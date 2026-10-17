"""DiscordImageCDN 與 wnacg 圖床流程的測試，用假的 Discord 頻道/討論串，不連外。"""
import asyncio
import itertools
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import discord

from functions import cdn_pages, discord_cdn, jm, nhentai, wnacg
from functions.discord_cdn import DiscordImageCDN

_ids = itertools.count(5000)


class FakeResponse:
    def __init__(self, body, delay):
        self.body, self.delay = body, delay

    async def __aenter__(self):
        await asyncio.sleep(self.delay)
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    async def read(self):
        return self.body

    async def text(self):
        return self.body.decode()


class FakeSession:
    def __init__(self, delay=0.01, pages=None):
        self.delay, self.pages, self.calls = delay, pages or {}, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return FakeResponse(self.pages.get(url, b"img:" + url.encode()), self.delay)


class FakeDiscord:
    """一個文字頻道加上它底下的討論串；附件網址的簽章到期時間可調整。"""

    def __init__(self, expires=None):
        self.expires = expires or (time.time() + 86400)
        self.channel = FakeChannel(self, 42)
        self.objects = {42: self.channel}
        self.sent = []  # [(thread_id, [filename, ...])]

    def attachment(self, thread_id, message_id, name):
        url = (f"https://cdn.discordapp.com/attachments/{thread_id}/{message_id}/{name}"
               f"?ex={int(self.expires):x}&is=0&hm=abc")
        return SimpleNamespace(filename=name, url=url)

    def bot(self, session):
        return SimpleNamespace(session=session, get_channel=self.objects.get,
                               get_partial_messageable=lambda cid: self.objects[cid],
                               fetch_channel=AsyncMock(side_effect=lambda cid: self.objects[cid]))


class FakeChannel:
    def __init__(self, world, channel_id):
        self.world, self.id, self.threads, self.archived = world, channel_id, [], []

    async def create_thread(self, name, type=None, auto_archive_duration=None):
        await asyncio.sleep(0.01)
        thread = FakeThread(self.world, next(_ids), name)
        self.threads.append(thread)
        self.world.objects[thread.id] = thread
        return thread

    async def archived_threads(self, limit=None):
        for thread in self.archived:
            yield thread


class FakeThread:
    def __init__(self, world, thread_id, name):
        self.world, self.id, self.name, self.messages = world, thread_id, name, []

    def _message(self, mid, names):
        return SimpleNamespace(id=mid, attachments=[self.world.attachment(self.id, mid, n) for n in names])

    async def send(self, files):
        await asyncio.sleep(0.01)
        mid = next(_ids)
        names = [f.filename for f in files]
        self.messages.append((mid, names))
        self.world.sent.append((self.id, names))
        return self._message(mid, names)

    async def history(self, limit=None, oldest_first=True):
        for mid, names in self.messages:
            yield self._message(mid, names)


def make_cdn(world=None, session=None):
    world = world or FakeDiscord()
    session = session or FakeSession()
    return DiscordImageCDN(world.bot(session), 42, use_http2=False), world, session


async def wait_until(predicate, rounds=300):
    for _ in range(rounds):
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return False


def replied(interaction):
    """翻頁回應用的參數：快速路徑是 response.edit_message，慢路徑是 defer 後 message.edit。"""
    if interaction.response.edit_message.await_count:
        return interaction.response.edit_message.call_args.kwargs
    return interaction.message.edit.call_args.kwargs


class DiscordImageCDNTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_once_into_gallery_thread(self):
        cdn, world, session = make_cdn()
        url1 = await cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg")
        url2 = await cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg")
        self.assertEqual(url1, url2)
        thread = world.channel.threads[0]
        self.assertEqual(thread.name, "wnacg-1")
        self.assertEqual(discord_cdn.thread_id_from_url(url1), thread.id)
        self.assertEqual(world.sent, [(thread.id, ["wnacg-1-1.jpg"])])
        self.assertEqual(session.calls, ["https://img/1.jpg"])

    async def test_concurrent_requests_share_one_upload_and_thread(self):
        cdn, world, _ = make_cdn()
        urls = await asyncio.gather(*(cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg") for _ in range(5)))
        self.assertEqual(len(set(urls)), 1)
        self.assertEqual(len(world.channel.threads), 1)
        self.assertEqual(sum(len(names) for _, names in world.sent), 1)

    async def test_prefetch_batches_ten_per_message(self):
        cdn, world, _ = make_cdn()
        cdn.prefetch("wnacg-1", [(f"wnacg-1-{n}", f"https://img/{n}.jpg") for n in range(1, 26)])
        self.assertTrue(await wait_until(lambda: all(cdn.cached(f"wnacg-1-{n}") for n in range(1, 26))))
        self.assertEqual([len(names) for _, names in world.sent], [10, 10, 5])
        self.assertEqual(len(world.channel.threads), 1)

    async def test_restart_recovers_index_from_embed_thread_hint(self):
        cdn, world, _ = make_cdn()
        url = await cdn.ensure("wnacg-1", "wnacg-1-3", "https://img/3.jpg")
        hint = discord_cdn.thread_id_from_url(url)

        restarted, _, session = make_cdn(world)  # 新實例 = 重開機，記憶體全空
        restarted._scan_done.set()  # 不靠掃描，只靠 embed 上的提示
        restarted.remember_thread("wnacg-1", hint)
        self.assertEqual(await restarted.ensure("wnacg-1", "wnacg-1-3", "https://img/3.jpg"), url)
        self.assertEqual(len(world.sent), 1)
        self.assertEqual(session.calls, [])

    async def test_restart_without_hint_finds_thread_by_scan(self):
        cdn, world, _ = make_cdn()
        url = await cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg")
        world.channel.archived, world.channel.threads = world.channel.threads, []  # 已被封存

        restarted, _, session = make_cdn(world)
        self.assertEqual(await restarted.lookup("wnacg-1", "wnacg-1-1"), url)
        self.assertEqual(session.calls, [])

    async def test_expired_signature_reloads_thread_without_reupload(self):
        world = FakeDiscord(expires=time.time() - 10)
        cdn, world, _ = make_cdn(world)
        old = await cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg")
        world.expires = time.time() + 86400
        new = await cdn.lookup("wnacg-1", "wnacg-1-1")
        self.assertNotEqual(old, new)
        self.assertTrue(discord_cdn.is_fresh(new))
        self.assertEqual(len(world.sent), 1)

    async def test_new_thread_waits_for_scan_instead_of_duplicating(self):
        cdn, world, _ = make_cdn()
        await cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg")
        old_thread = world.channel.threads[0]
        world.channel.archived, world.channel.threads = [old_thread], []

        restarted, _, _ = make_cdn(world)
        gate = asyncio.Event()
        original_scan = restarted._scan_threads

        async def slow_scan():
            await gate.wait()  # 掃描很久才完成（超過舊的 10 秒等待）
            await original_scan()

        restarted._scan_threads = slow_scan
        original_wait = discord_cdn.SCAN_WAIT
        discord_cdn.SCAN_WAIT = 0.01
        try:
            restarted.prefetch("wnacg-1", [("wnacg-1-2", "https://img/2.jpg")])
            await asyncio.sleep(0.1)
            self.assertEqual(world.channel.threads, [])  # 掃描完成前不會開新串
            gate.set()
            self.assertTrue(await wait_until(lambda: restarted.cached("wnacg-1-2")))
        finally:
            discord_cdn.SCAN_WAIT = original_wait
        self.assertEqual(world.channel.threads, [])
        self.assertEqual(world.sent[-1][0], old_thread.id)  # 傳進原本的討論串

    async def test_failed_download_returns_none(self):
        class BrokenSession(FakeSession):
            def get(self, url, **kwargs):
                raise OSError("boom")
        cdn, world, _ = make_cdn(session=BrokenSession())
        self.assertIsNone(await cdn.ensure("wnacg-1", "wnacg-1-1", "https://img/1.jpg"))
        self.assertEqual(world.sent, [])


GALLERY_JS = (
    'document.writeln("var imglist = [{ url: fast_img_host+\\"//img5.qy0.ru/data/1/01.jpg?verify=a\\", caption: \\"[01]\\"},'
    '{ url: fast_img_host+\\"//img5.qy0.ru/data/1/02.jpg?verify=b\\", caption: \\"[02]\\"},'
    '{ url: fast_img_host+\\"//img5.qy0.ru/data/1/03.jpg?verify=c\\", caption: \\"[03]\\"},'
    '{ url: fast_img_host+\\"/themes/weitu/images/bg/shoucang.jpg\\", caption: \\"\\"}];");'
)


def gallery_session(aid):
    return FakeSession(pages={f"https://www.wnacg.com/photos-gallery-aid-{aid}.html": GALLERY_JS.encode()})


def old_embed(aid, page=2):
    """舊版訊息：圖片是原站網址，embed.url 沒有圖床索引。"""
    embed = discord.Embed(title="t", url=f"https://www.wnacg.com/photos-index-page-1-aid-{aid}.html")
    embed.set_image(url="https://img5.qy0.ru/data/1/02.jpg?verify=old")
    embed.set_footer(text=str(page))
    embed.add_field(name="頁數", value="3")
    embed.set_author(name="wnacg")
    return embed


class WnacgCDNTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cdn_pages._prefetch_done.clear()
        cdn_pages._prefetch_running.clear()

    async def test_gallery_images_skip_ad_image(self):
        images = await wnacg.fetch_gallery_images(gallery_session("901"), "901")
        self.assertEqual(images, [f"https://img5.qy0.ru/data/1/0{n}.jpg?verify={c}" for n, c in zip((1, 2, 3), "abc")])

    async def test_page_image_is_cdn_and_whole_gallery_prefetched(self):
        session = gallery_session("902")
        cdn, world, _ = make_cdn(session=session)
        url = await wnacg.get_page_image(session, cdn, "902", 2)
        self.assertTrue(url.startswith("https://cdn.discordapp.com/"))
        self.assertTrue(await wait_until(lambda: all(cdn.cached(wnacg.cdn_key("902", n)) for n in (1, 2, 3))))
        sent_before, calls_before = len(world.sent), len(session.calls)
        jumped = await wnacg.get_page_image(session, cdn, "902", 3)
        self.assertTrue(jumped.startswith("https://cdn.discordapp.com/"))
        self.assertEqual((len(world.sent), len(session.calls)), (sent_before, calls_before))

    async def test_apply_page_records_thread_on_embed(self):
        session = gallery_session("904")
        cdn, world, _ = make_cdn(session=session)
        embed = old_embed("904")
        self.assertIsNone(wnacg.embed_thread_hint(embed))
        img = await wnacg.get_page_image(session, cdn, "904", 1)
        wnacg.apply_page(embed, img, 1, cdn, "904")
        thread_id = world.channel.threads[0].id
        self.assertTrue(embed.url.endswith(f"aid-904.html#cdn={thread_id}"))
        self.assertEqual(wnacg.embed_thread_hint(embed), thread_id)
        self.assertEqual(embed.footer.text, "1")
        # 再套一次不會重複疊加 #cdn=
        wnacg.apply_page(embed, img, 1, cdn, "904")
        self.assertEqual(embed.url.count("#cdn="), 1)

    async def test_old_embed_upgraded_on_page_turn(self):
        session = gallery_session("905")
        cdn, world, _ = make_cdn(session=session)
        view = wnacg.NumberView2(session=session)
        embed = old_embed("905", page=2)
        message = SimpleNamespace(id=next(_ids), embeds=[embed], edit=AsyncMock())
        interaction = SimpleNamespace(client=SimpleNamespace(image_cdn=cdn), message=message,
                                      response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()))
        await view._go(interaction, lambda current, total: min(total, current + 1))
        edited = replied(interaction)["embed"]
        self.assertEqual(edited.footer.text, "3")
        # 還沒上圖床的頁直接附在這次編輯上（一次 API 呼叫），討論串那份在背景補上
        self.assertEqual(edited.image.url, "attachment://wnacg-905-3.jpg")
        self.assertEqual([f.filename for f in replied(interaction)["attachments"]], ["wnacg-905-3.jpg"])
        self.assertIn("#cdn=", edited.url)
        self.assertEqual(view.middle_button.label, "3/3")
        self.assertTrue(await wait_until(lambda: cdn.cached("wnacg-905-3")))
        # 已在圖床的頁：圖片用 CDN 網址，並清掉先前附在訊息上的圖
        interaction.response.edit_message.reset_mock()
        embed.set_footer(text="2")
        await view._go(interaction, lambda current, total: min(total, current + 1))
        self.assertTrue(replied(interaction)["embed"].image.url.startswith("https://cdn.discordapp.com/"))
        self.assertEqual(replied(interaction)["attachments"], [])

    async def test_without_channel_returns_source_url(self):
        session = gallery_session("903")
        cdn = DiscordImageCDN(SimpleNamespace(session=session), 0, use_http2=False)
        url = await wnacg.get_page_image(session, cdn, "903", 1)
        self.assertEqual(url, "https://img5.qy0.ru/data/1/01.jpg?verify=a")


def host_convert(image, piece):
    """host.py 的 convertImg（numpy 版），拿來對照 bot 內的 PIL 版。"""
    import numpy as np
    from PIL import Image
    if piece <= 1:
        return image
    arr = np.array(image)
    block = arr.shape[0] // piece
    chunks = [arr[i * block:] if i == piece - 1 else arr[i * block:(i + 1) * block] for i in range(piece)]
    return Image.fromarray(np.vstack(chunks[::-1]))


def make_png(width=40, height=103):
    """每一列顏色不同的測試圖，用 PNG 無損比較。"""
    import io
    from PIL import Image
    image = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel((x, y), (y * 2 % 256, x * 5 % 256, (x + y) % 256))
    out = io.BytesIO()
    image.save(out, "PNG")
    return image, out.getvalue()


class JmAndNhentaiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cdn_pages._prefetch_done.clear()
        cdn_pages._prefetch_running.clear()

    def test_jm_pieces_match_host_rules(self):
        self.assertEqual(jm.jm_pieces(200000, "00001"), 1)
        self.assertEqual(jm.jm_pieces(250000, "00001"), 10)
        for album in (300000, 622529):
            for page in ("00001", "00007", "00120"):
                piece = jm.jm_pieces(album, page)
                self.assertIn(piece, [2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
                if album >= 421926:
                    self.assertLessEqual(piece, 16)

    def test_jm_descramble_matches_host_convert(self):
        import io
        import numpy as np
        from PIL import Image
        original, png = make_png()
        for album, page in ((622529, "00001"), (300000, "00002"), (622529, "00007")):
            piece = jm.jm_pieces(album, page)
            expected = np.asarray(host_convert(original, piece), dtype=float)
            data, ext = jm.jm_descramble(album, page, png)
            got = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype=float)
            self.assertEqual(ext, ".webp")
            self.assertEqual(got.shape, expected.shape)
            self.assertLess(np.abs(got - expected).mean(), 8)  # 只差有損壓縮

    async def test_jm_page_uploads_descrambled_jpeg(self):
        _, png = make_png()
        session = FakeSession(pages={jm.jm_source(622529, 1): png})
        cdn, world, _ = make_cdn(session=session)
        url = await jm.jm_page_image(cdn, 622529, 1)
        self.assertTrue(url.startswith("https://cdn.discordapp.com/"))
        self.assertEqual(world.channel.threads[0].name, "jm-622529")
        self.assertEqual(world.sent[0][1], ["jm-622529-1.webp"])

    async def test_jm_without_channel_uses_host_url(self):
        cdn = DiscordImageCDN(SimpleNamespace(session=FakeSession()), 0, use_http2=False)
        self.assertEqual(await jm.jm_page_image(cdn, 622529, 3), jm.jm_legacy_url(622529, 3))

    async def test_jm_old_embed_upgraded_on_page_turn(self):
        _, png = make_png()
        session = FakeSession(pages={jm.jm_source(622529, n): png for n in (1, 2, 3)})
        cdn, world, _ = make_cdn(session=session)
        embed = discord.Embed(title="t", url="https://18comic.vip/album/622529/")
        embed.set_image(url=jm.jm_legacy_url(622529, 1))
        embed.add_field(name="頁數", value="3")
        message = SimpleNamespace(id=next(_ids), embeds=[embed], edit=AsyncMock())
        interaction = SimpleNamespace(client=SimpleNamespace(image_cdn=cdn), message=message,
                                      response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()))
        await jm.NumberView3()._go(interaction, lambda current, total: min(total, current + 1))
        edited = replied(interaction)["embed"]
        self.assertEqual(edited.footer.text, "2")
        self.assertIn("jm-622529-2.webp", edited.image.url)
        self.assertIn("#cdn=", edited.url)

    async def test_nhentai_page_turn_uses_index_without_recrawl(self):
        links = [f"https://i3.nhentai.net/galleries/9/{n}.jpg" for n in (1, 2, 3)]
        session = FakeSession()
        cdn, world, _ = make_cdn(session=session)
        crawl = AsyncMock(return_value=("t", "thumb", {}, links[0], links))
        original = nhentai.cached_nhentai_crawl
        nhentai.cached_nhentai_crawl = crawl
        try:
            embed = discord.Embed(title="t", url="https://nhentai.net/g/680635/")
            embed.set_image(url=links[0])  # 舊版：原圖網址、沒有 footer
            embed.add_field(name="頁數", value="3")
            message = SimpleNamespace(id=next(_ids), embeds=[embed], edit=AsyncMock())
            interaction = SimpleNamespace(client=SimpleNamespace(image_cdn=cdn), message=message,
                                          response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()))
            view = nhentai.NumberView(session=session, sec5h=None)
            await view._go(interaction, lambda current, total: min(total, current + 1))
            edited = replied(interaction)["embed"]
            self.assertEqual(edited.footer.text, "2")
            self.assertIn("nhentai-680635-2.jpg", edited.image.url)
            self.assertTrue(await wait_until(lambda: all(cdn.cached(f"nhentai-680635-{n}") for n in (1, 2, 3))))
            calls = crawl.await_count
            await view._go(interaction, lambda current, total: total)
            self.assertIn("nhentai-680635-3.jpg", replied(interaction)["embed"].image.url)
            self.assertEqual(crawl.await_count, calls)  # 命中索引就不再爬 nhentai
        finally:
            nhentai.cached_nhentai_crawl = original

    async def test_large_images_split_across_messages(self):
        big = b"x" * (4 * 1024 * 1024)
        session = FakeSession(pages={f"https://img/{n}.jpg": big for n in range(1, 4)})
        cdn, world, _ = make_cdn(session=session)
        await cdn._upload("g", [(f"g-{n}", f"https://img/{n}.jpg") for n in range(1, 4)])
        self.assertEqual([len(names) for _, names in world.sent], [2, 1])

    async def test_inline_first_page_attaches_file_and_indexes_in_background(self):
        session = gallery_session("906")
        cdn, world, _ = make_cdn(session=session)
        img = await wnacg.get_page_image(session, cdn, "906", 1, inline=True)
        self.assertEqual(img, "attachment://wnacg-906-1.jpg")
        self.assertEqual(world.sent, [])  # 回覆訊息不必等討論串上傳
        embed = old_embed("906", page=1)
        wnacg.apply_page(embed, img, 1, cdn, "906")
        self.assertTrue(embed.url.endswith("#cdn=0"))
        self.assertEqual(wnacg.embed_thread_hint(embed), 0)
        files = cdn_pages.cdn_files(embed)["files"]
        self.assertEqual(files[0].filename, "wnacg-906-1.jpg")
        self.assertEqual(cdn_pages.cdn_files(embed), {})
        # 背景預載把整本（含第 1 頁）傳進討論串，第 1 頁不再重新下載
        self.assertTrue(await wait_until(lambda: all(cdn.cached(f"wnacg-906-{n}") for n in (1, 2, 3))))
        page1 = "https://img5.qy0.ru/data/1/01.jpg?verify=a"
        self.assertEqual(session.calls.count(page1), 1)

    async def test_sources_fall_back_in_order(self):
        class MirrorSession(FakeSession):
            def get(self, url, **kwargs):
                self.calls.append(url)
                if "broken" in url:
                    raise OSError("down")
                return FakeResponse(url.encode(), 0.01)
        cdn, _, session = make_cdn(session=MirrorSession())
        self.assertEqual(await cdn._download(("https://a/1.jpg", "https://b/1.jpg")), b"https://a/1.jpg")
        self.assertEqual(session.calls, ["https://a/1.jpg"])  # 第一個成功就不碰第二個
        self.assertEqual(await cdn._download(("https://broken/1.jpg", "https://b/1.jpg")), b"https://b/1.jpg")
        self.assertEqual(nhentai.nh_sources("https://i7.nhentai.net/galleries/9/1.webp"),
                         ("https://i3.nhentai.net/galleries/9/1.webp", "https://i7.nhentai.net/galleries/9/1.webp"))
        self.assertEqual(nhentai.nh_sources("https://i3.nhentai.net/galleries/9/1.webp"),
                         "https://i3.nhentai.net/galleries/9/1.webp")

    async def test_view_link_uses_its_own_image_without_gallery_list(self):
        session = FakeSession()
        cdn, world, _ = make_cdn(session=session)
        src = "https://img5.qy0.ru/data/1/05.jpg?verify=v"
        img = await wnacg.get_page_image(session, cdn, "907", 5, inline=True, first_src=src)
        self.assertEqual(img, "attachment://wnacg-907-5.jpg")
        self.assertEqual(session.calls[0], src)  # 第一個請求就是該頁圖片，不必先抓整本清單

    async def test_crawl_caches_success_only(self):
        calls = []

        async def fake(session, digit):
            calls.append(digit)
            if digit == "bad":
                raise RuntimeError("HTTP 404")
            return ("t", "thumb", "3", [], "link")

        original = wnacg._wnacg_crawl_cached
        wnacg._wnacg_crawl_cached = wnacg.async_ttl_cache(ttl_seconds=60, key_arg="digit")(fake)
        try:
            self.assertEqual(await wnacg.wnacg_crawl(None, 908), await wnacg.wnacg_crawl(None, "908"))
            self.assertEqual(await wnacg.wnacg_crawl(None, "bad"), 404)
            self.assertEqual(await wnacg.wnacg_crawl(None, "bad"), 404)
            self.assertEqual(calls, ["908", "bad", "bad"])
        finally:
            wnacg._wnacg_crawl_cached = original

    async def test_nhentai_old_embed_page_formats(self):
        proxy = "https://proxy.example.workers.dev"
        cases = {
            "https://i3.nhentai.net/galleries/4177447/5.webp": 5,
            "https://i3.nhentai.net/galleries/4177447/5.webp?123": 5,  # 舊重新整理鈕
            f"{proxy}?img=https://i3.nhentai.net/galleries/4177447/5.jpg": 5,
            f"{proxy}?img=https://i3.nhentai.net/galleries/4177447/5.jpg?77": 5,
            "https://cdn.discordapp.com/attachments/1/2/nhentai-680635-12.jpg?ex=1&is=2&hm=3": 12,
        }
        for url, page in cases.items():
            view = nhentai.NumberView(session=None, sec5h=None)
            view._sync_number(SimpleNamespace(image=SimpleNamespace(url=url), footer=None))
            self.assertEqual(view.number, page, url)

    async def test_fast_page_turn_uses_single_api_call(self):
        interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()),
                                      message=SimpleNamespace(edit=AsyncMock()))

        async def work():
            return {"embed": "e"}

        await cdn_pages.reply_with_edit(interaction, work)
        interaction.response.edit_message.assert_awaited_once_with(embed="e")
        interaction.response.defer.assert_not_awaited()
        interaction.message.edit.assert_not_awaited()

    async def test_slow_page_turn_defers_then_edits(self):
        interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()),
                                      message=SimpleNamespace(edit=AsyncMock()))

        async def work():
            await asyncio.sleep(0.05)
            return {"embed": "e"}

        original = cdn_pages.FAST_REPLY
        cdn_pages.FAST_REPLY = 0.01
        try:
            await cdn_pages.reply_with_edit(interaction, work)
        finally:
            cdn_pages.FAST_REPLY = original
        interaction.response.defer.assert_awaited_once()
        interaction.message.edit.assert_awaited_once_with(embed="e")
        interaction.response.edit_message.assert_not_awaited()

    async def test_jump_to_uncached_page_prefetches_next_pages(self):
        cdn, world, _ = make_cdn()
        cdn_pages._prefetch_done["g"] = time.time() + 10 ** 9  # 擋掉整本預載，只看跳頁視窗

        async def src_of(n):
            return f"https://img/{n}.jpg"

        url = await cdn_pages.cdn_page_image(cdn, "g", 10, src_of, total=20)
        self.assertIsNotNone(url)
        self.assertTrue(await wait_until(lambda: all(cdn.cached(f"g-{n}") for n in (11, 12, 13))))
        self.assertFalse(cdn.cached("g-14"))

    async def test_page_turn_locks_are_per_message(self):
        release = asyncio.Event()
        order = []

        async def slow():
            async with cdn_pages.message_lock(1):
                await release.wait()
                order.append("slow")

        async def fast():
            async with cdn_pages.message_lock(2):
                order.append("fast")

        slow_task = asyncio.create_task(slow())
        await asyncio.sleep(0)
        await asyncio.wait_for(fast(), 1)  # 另一則訊息不會被卡住
        release.set()
        await slow_task
        self.assertEqual(order, ["fast", "slow"])

    def test_jm_crawl_cached_success_only(self):
        calls = []

        def fake(url):
            calls.append(url)
            if "bad" in url:
                raise RuntimeError("blocked")
            return ("title", 3, 622529, {})

        original = jm.jm_crawl
        jm.jm_crawl = fake
        jm._jm_crawl_cache.clear()
        try:
            url = "https://18comic.vip/album/622529/"
            self.assertEqual(jm.jm_crawl_cached(url), jm.jm_crawl_cached(url))
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    jm.jm_crawl_cached("https://18comic.vip/album/bad/")
            self.assertEqual(calls, [url, "https://18comic.vip/album/bad/", "https://18comic.vip/album/bad/"])
        finally:
            jm.jm_crawl = original
            jm._jm_crawl_cache.clear()

    async def test_slash_reply_fast_and_slow(self):
        def make():
            return SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
                                   followup=SimpleNamespace(send=AsyncMock()))

        async def fast():
            return {"content": "ok"}

        async def slow():
            await asyncio.sleep(0.05)
            return {"content": "ok"}

        interaction = make()
        await cdn_pages.reply_with_send(interaction, fast)
        interaction.response.send_message.assert_awaited_once_with(content="ok")
        interaction.response.defer.assert_not_awaited()

        interaction = make()
        original = cdn_pages.FAST_REPLY
        cdn_pages.FAST_REPLY = 0.01
        try:
            await cdn_pages.reply_with_send(interaction, slow)
        finally:
            cdn_pages.FAST_REPLY = original
        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once_with(content="ok")

    async def test_user_pages_jump_ahead_of_bulk_prefetch(self):
        cdn, world, _ = make_cdn()
        cdn._scan_done.set()
        cdn.prefetch_workers = 1
        cdn.prefetch("bulk", [(f"bulk-{n}", f"https://img/b{n}.jpg") for n in range(1, 41)], priority=1)
        cdn.prefetch("user", [("user-7", "https://img/u7.jpg")], priority=0)
        self.assertTrue(await wait_until(lambda: cdn.cached("user-7")))
        # 整本 40 頁切成 4 批；使用者的頁最多只等正在處理的那一批
        bulk_before = sum(1 for thread_id, names in world.sent
                          if names[0].startswith("bulk") and world.sent.index((thread_id, names)) <
                          next(i for i, (_, n) in enumerate(world.sent) if n[0].startswith("user")))
        self.assertLessEqual(bulk_before, 1)

    async def test_preloaded_bytes_dropped_when_page_already_uploaded(self):
        cdn, world, _ = make_cdn()
        await cdn.ensure("g", "g-1", "https://img/1.jpg")
        cdn.preload("g-1", b"dup", ".jpg")
        cdn.prefetch("g", [("g-1", "https://img/1.jpg")], priority=0)
        self.assertTrue(await wait_until(lambda: "g-1" not in cdn._preloaded))
        self.assertEqual(len(world.sent), 1)

    def test_current_page_sources(self):
        embed = discord.Embed(url="https://x")
        embed.set_image(url="https://cdn.discordapp.com/attachments/1/2/nhentai-5-7.jpg?ex=1&is=2&hm=3")
        self.assertEqual(cdn_pages.current_page(embed), 7)
        embed.set_footer(text="9")
        self.assertEqual(cdn_pages.current_page(embed), 9)


if __name__ == "__main__":
    unittest.main()

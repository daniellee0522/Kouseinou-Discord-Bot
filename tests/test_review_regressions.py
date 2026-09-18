"""Regression tests without live credentials, bot startup, or external requests."""
import ast
import asyncio
import importlib.util
import json
import logging
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

ROOT = Path(__file__).resolve().parents[1]


def method(file, name, namespace=None):
    tree = ast.parse((ROOT / file).read_text())
    node = next(n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    ns = {'discord': discord, 're': re, 'asyncio': asyncio}
    ns.update(namespace or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), ns)
    return ns[name]


class ReviewRegressionTests(unittest.IsolatedAsyncioTestCase):
    def test_persistent_views_read_each_message_page(self):
        for file in ['functions/jm.py', 'functions/nhentai.py']:
            sync = method(file, '_sync_number', {
                'extract_page_number': lambda url: int(re.search(r'/(\d+)\.webp$', url)[1])})
            view = SimpleNamespace(number=1, _page_synced=False)
            for page in (3, 20, 1):
                sync(view, SimpleNamespace(image=SimpleNamespace(url=f'https://example.com/{page}.webp')))
                self.assertEqual(view.number, page, file)

    async def test_disabled_facebook_does_not_fetch(self):
        fetch = AsyncMock()
        ban = Mock(return_value=True)
        handler = method('cmds/events.py', 'handler_facebook',
                         {'get_facebook_data': fetch, 'is_embed_ban': ban})
        await handler(None, SimpleNamespace(guild=SimpleNamespace(id=42)), 'https://facebook.com/post', None)
        ban.assert_called_once_with(server_id=42, arg='fb')
        fetch.assert_not_awaited()

    async def test_wnacg_links_obey_nsfw_gate(self):
        view = SimpleNamespace(is_nsfw_channel=lambda channel: False)
        for name in ['handler_wnacg', 'handler_wnacg_view']:
            handler = method('cmds/events.py', name)
            await handler(view, SimpleNamespace(channel=object()), 'https://example.com', None)

    def test_nsfw_channel_types(self):
        check = method('cmds/events.py', 'is_nsfw_channel')
        self.assertTrue(check(None, SimpleNamespace(guild=None)))
        self.assertFalse(check(None, SimpleNamespace(guild=object(), is_nsfw=lambda: False)))
        self.assertTrue(check(None, SimpleNamespace(guild=object(), is_nsfw=lambda: True)))
        thread = Mock(spec=discord.Thread)
        thread.guild = object()
        thread.parent = None
        self.assertFalse(check(None, thread))

    def test_missing_or_invalid_cookies(self):
        load = method('functions/facebook_fetch_new.py', 'load_cookies',
                      {'config': SimpleNamespace(DATA_DIR=Path('/unused')), 'json': json, 'logging': logging})
        for error in [FileNotFoundError(), json.JSONDecodeError('invalid', '', 0)]:
            with patch('builtins.open', side_effect=error):
                self.assertEqual(load(), {})

    async def test_failed_search_has_no_retry_queue_dependency(self):
        command = method('cmds/hentai_embed_cmd.py', 'missav', {
            'fetch_missav_embed': AsyncMock(side_effect=RuntimeError('unavailable')),
            'missav_fallback_embed': AsyncMock(return_value=None)})
        interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),
                                      followup=SimpleNamespace(send=AsyncMock()))
        bot = SimpleNamespace(missav_crawl=object(), jable_crawl=object())
        await command(SimpleNamespace(bot=bot), interaction, 'TEST-001')
        interaction.followup.send.assert_awaited_once_with('目前無法取得資料，請稍後再試。')

    async def test_jump_preserves_clients_and_defers_before_fetch(self):
        response = SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock())
        interaction = SimpleNamespace(response=response, followup=SimpleNamespace(send=AsyncMock()))
        embed = discord.Embed(url='https://nhentai.net/g/123/')
        embed.set_author(name='nhentai')
        embed.add_field(name='頁數', value='5')
        target = SimpleNamespace(embeds=[embed], edit=AsyncMock())
        bot = SimpleNamespace(session=object(), missav_crawl=object())
        async def crawl(*args):
            response.defer.assert_awaited_once_with(ephemeral=True)
            return None, None, None, None, ['https://example.com/1.jpg', 'https://example.com/2.jpg']
        view_factory = Mock(return_value=SimpleNamespace(middle_button=SimpleNamespace(label='')))
        submit = method('cmds/jumppage.py', 'on_submit', {
            'Interaction': discord.Interaction, 'nhentai_crawl': crawl,
            'extract_numbers': lambda url: ('123', None), 'NumberView': view_factory})
        await submit(SimpleNamespace(bot=bot, target_message=target,
                                     page_input=SimpleNamespace(value='2')), interaction)
        view_factory.assert_called_once_with(session=bot.session, sec5h=bot.missav_crawl)
        self.assertEqual(embed.image.url, 'https://example.com/2.jpg')
        interaction.followup.send.assert_awaited_once()

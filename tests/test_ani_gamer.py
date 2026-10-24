"""動畫瘋訂閱 / 輪詢的回歸測試；不連外網。"""
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from functions import ani_gamer


def _card(name, episode, date, hours, sn, labels=()):
    label_html = ''.join(f"<span class='label-edition'>{label}</span>" for label in labels)
    return f"""
    <div class='newanime-date-area new-count-1 fadeIn'>
      <div class='anime-content-block'><div class='anime-block'>
        <a class='anime-card-block' href='animeVideo.php?sn={sn}'>
          <div class='anime-pic-block'>
            <div class='anime-hours-block'><img src='x.svg'><span class='anime-hours'>{hours}</span></div>
            <div class='anime-blocker'><img class='lazyload' src='data:' data-src='https://img.example/{sn}.jpg'></div>
          </div>
          <div class='anime-detail-block'>
            <div class='anime-detail-info-block'>
              <div class='anime-episode'><img src='tv.svg'><p>{episode}</p></div>
              <div class='anime-label-block'>{label_html}</div>
            </div>
            <div class='anime-name-block'><p class='anime-name'>{name}</p></div>
          </div>
        </a>
      </div></div>
      <span class='anime-date-info'><svg><title>t</title></svg> {date} </span>
    </div>"""


def _schedule(days):
    html = "<div class='programlist-block'>"
    for title, items in days.items():
        html += f"<div class='day-list'><h3 class='day-title'>{title}</h3>"
        for name, hours in items:
            html += (f"<a class='text-anime-info'><span class='text-anime-time'>{hours}</span>"
                     f"<div class='text-anime-detail'><p class='text-anime-name'>{name}</p></div></a>")
        html += "</div>"
    return html + "</div>"


def _page(cards, days=None):
    return ("<html><body><div class='newanime-wrap timeline-ver'><div class='newanime-block'>"
            + ''.join(cards) + "</div></div>" + _schedule(days or {}) + "</body></html>")


PAGE = _page([
    _card('BLEACH 死神', '第48集', '10/18 (日)', '23:00', 1),
    _card('黑化吧！聖女大人', '第3集', '10/14 (三)', '22:00', 2, labels=['付費會員', '年齡限制']),
    _card('來自遠方', '第2集', '10/12 (一)', '00:00', 3),
], days={'週一': [('來自遠方', '00:00')], '週日': [('BLEACH 死神', '23:00')]})


class ParseTests(unittest.TestCase):
    def test_parses_timeline_and_r18_label_anywhere(self):
        entries = {e['name']: e for e in ani_gamer.parse_timeline(PAGE)}
        self.assertEqual(set(entries), {'BLEACH 死神', '黑化吧！聖女大人(年齡限制)', '來自遠方'})
        bleach = entries['BLEACH 死神']
        self.assertEqual((bleach['weekday'], bleach['time'], bleach['episode']), (7, '2300', '第48集'))
        self.assertEqual(bleach['href'], 'https://ani.gamer.com.tw/animeVideo.php?sn=1')

    def test_keeps_latest_episode_when_listed_twice(self):
        page = _page([_card('A', '第3集', '10/18 (日)', '23:00', 1),
                      _card('A', '第4集', '10/18 (日)', '23:00', 2)])
        self.assertEqual(ani_gamer.parse_timeline(page)[0]['episode'], '第4集')

    def test_parses_weekly_schedule(self):
        self.assertEqual(ani_gamer.parse_schedule(PAGE),
                         {'來自遠方': (1, '0000'), 'BLEACH 死神': (7, '2300')})

    def test_episode_comparison_is_numeric(self):
        self.assertTrue(ani_gamer.is_newer_episode('第10集', '第9集'))
        self.assertFalse(ani_gamer.is_newer_episode('第9集', '第10集'))
        self.assertTrue(ani_gamer.is_newer_episode('第12.5集', '第12集'))


class SubsFileTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        patcher = patch.object(ani_gamer.config, 'DATA_DIR', self.data_dir, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        fetch = patch.object(ani_gamer, '_fetch_homepage', side_effect=lambda: self.page)
        fetch.start()
        self.addCleanup(fetch.stop)
        self.page = PAGE
        self.write({})

    def write(self, data):
        (self.data_dir / 'sub.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')

    def read(self):
        return json.loads((self.data_dir / 'sub.json').read_text(encoding='utf8'))


class SubscribeTests(SubsFileTestCase):
    def test_lowercase_input_does_not_subscribe_twice(self):
        self.assertEqual(ani_gamer.anime_get_info_add('BLEACH', 1), 'BLEACH 死神')
        self.assertEqual(ani_gamer.anime_get_info_add('bleach', 1), 'repeated')
        self.assertEqual(len(self.read()['1']), 1)

    def test_button_name_with_r18_suffix_is_found(self):
        name = ani_gamer.anime_get_info('聖女', 'R')[0]
        self.assertEqual(name, '黑化吧！聖女大人(年齡限制)')
        self.assertEqual(ani_gamer.anime_get_info_add(name, 1, 'Y'), name)

    def test_subscription_uses_weekly_schedule(self):
        ani_gamer.anime_get_info_add('來自', 1)
        sub = self.read()['1'][0]
        self.assertEqual((sub['update_date'], sub['update_time'], sub['episode']), (1, '0000', '第2集'))

    def test_connection_failure_returns_none(self):
        self.page = None
        self.assertIsNone(ani_gamer.anime_get_info_add('BLEACH', 1))

    def test_remove_prefers_matching_r18_version(self):
        self.write({'1': [{'name': '聖女'}, {'name': '聖女(年齡限制)'}]})
        self.assertEqual(ani_gamer.remove_subscription(1, '聖女'), '聖女')
        self.assertEqual(ani_gamer.remove_subscription(1, '聖女', 'R'), '聖女(年齡限制)')
        self.assertEqual(self.read(), {})
        self.assertIsNone(ani_gamer.remove_subscription(1, '聖女'))

    def test_remove_r18_when_only_normal_version(self):
        self.write({'1': [{'name': '聖女'}]})
        self.assertEqual(ani_gamer.remove_subscription(1, '聖女', 'R'), 'no r18')


class PollTests(SubsFileTestCase):
    def sub(self, **kw):
        base = {'name': 'BLEACH 死神', 'episode': '第47集', 'update_date': 7, 'update_time': '2300'}
        base.update(kw)
        return base

    def test_notifies_once_per_new_episode(self):
        self.write({'1': [self.sub()], '2': [self.sub()]})
        notifications, removed = ani_gamer.poll_updates()
        self.assertEqual(sorted(s for s, _ in notifications), ['1', '2'])
        self.assertEqual(notifications[0][1]['episode'], '第48集')
        self.assertEqual(removed, [])
        self.assertEqual(ani_gamer.poll_updates(), ([], []))

    def test_existing_duplicate_subscription_notifies_once(self):
        self.write({'1': [self.sub(), self.sub()]})
        notifications, _ = ani_gamer.poll_updates()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(len(self.read()['1']), 1)

    def test_stale_older_page_does_not_renotify(self):
        self.write({'1': [self.sub(episode='第48集')]})
        self.page = _page([_card('BLEACH 死神', '第47集', '10/11 (日)', '23:00', 1)])
        self.assertEqual(ani_gamer.poll_updates(), ([], []))
        self.assertEqual(self.read()['1'][0]['episode'], '第48集')

    def test_rescheduled_anime_syncs_time_without_new_episode(self):
        self.write({'1': [self.sub(episode='第48集')]})
        self.page = _page([_card('BLEACH 死神', '第48集', '10/18 (日)', '23:00', 1)],
                          days={'週一': [('BLEACH 死神', '00:30')]})
        self.assertEqual(ani_gamer.poll_updates(), ([], []))
        sub = self.read()['1'][0]
        self.assertEqual((sub['update_date'], sub['update_time']), (1, '0030'))

    def test_missing_anime_is_removed_only_after_limit(self):
        self.write({'1': [self.sub(name='已完結'), self.sub()]})
        ani_gamer.poll_updates()
        self.assertEqual([s['name'] for s in self.read()['1']], ['已完結', 'BLEACH 死神'])
        data = self.read()
        data['1'][0]['missing_since'] -= ani_gamer.MISSING_LIMIT_SEC
        self.write(data)
        _, removed = ani_gamer.poll_updates()
        self.assertEqual(removed, [('1', '已完結')])
        self.assertEqual([s['name'] for s in self.read()['1']], ['BLEACH 死神'])

    def test_empty_or_failed_page_changes_nothing(self):
        original = {'1': [self.sub()]}
        self.write(original)
        for page in (None, '<html></html>'):
            self.page = page
            self.assertEqual(ani_gamer.poll_updates(), ([], []))
        self.assertEqual(self.read(), original)



def _tw(*args):
    return ani_gamer.TW_TZ.localize(datetime.datetime(*args)).timestamp()


class FastPollTests(unittest.TestCase):
    # 2026-10-18 是星期日(7)，2026-10-19 是星期一(1)
    SUB = {'name': 'A', 'episode': '第1集', 'update_date': 7, 'update_time': '2300'}

    def delay(self, subs, now):
        return ani_gamer.seconds_until_fast_poll({'1': subs}, now)

    def test_fast_inside_air_window_until_notified(self):
        self.assertEqual(self.delay([dict(self.SUB)], _tw(2026, 10, 18, 22, 59, 30)), 0)
        self.assertEqual(self.delay([dict(self.SUB)], _tw(2026, 10, 18, 23, 20)), 0)
        notified = dict(self.SUB, notified_at=_tw(2026, 10, 18, 23, 0, 5))
        self.assertGreater(self.delay([notified], _tw(2026, 10, 18, 23, 1)), 0)

    def test_waits_until_next_window_start(self):
        wait = self.delay([dict(self.SUB)], _tw(2026, 10, 18, 22, 50))
        self.assertEqual(wait, 9 * 60)

    def test_window_crossing_week_boundary(self):
        sub = dict(self.SUB, update_time='2350')
        self.assertEqual(self.delay([sub], _tw(2026, 10, 19, 0, 10)), 0)

    def test_after_window_falls_back(self):
        self.assertGreater(self.delay([dict(self.SUB)], _tw(2026, 10, 18, 23, 40)), 0)
        self.assertIsNone(ani_gamer.seconds_until_fast_poll({}, _tw(2026, 10, 18, 23, 0)))

    def test_next_poll_delay_caps_at_normal_interval(self):
        with patch.object(ani_gamer, '_load_subs', return_value={'1': [dict(self.SUB)]}):
            self.assertEqual(ani_gamer.next_poll_delay(10, 180, _tw(2026, 10, 18, 23, 0)), 10)
            self.assertEqual(ani_gamer.next_poll_delay(10, 180, _tw(2026, 10, 18, 22, 58)), 60)
            self.assertEqual(ani_gamer.next_poll_delay(10, 180, _tw(2026, 10, 18, 12, 0)), 180)

    def test_poll_records_notified_at(self):
        data = {'1': [{'name': 'BLEACH 死神', 'episode': '第47集'}]}
        ani_gamer.apply_updates(data, ani_gamer.parse_timeline(PAGE), {}, now=123.0)
        self.assertEqual(data['1'][0]['notified_at'], 123.0)


if __name__ == '__main__':
    unittest.main()

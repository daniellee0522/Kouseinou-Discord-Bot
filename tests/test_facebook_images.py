"""Image ownership regressions; no credentials or network required."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import mock_open, patch

MODULE = Path(__file__).resolve().parents[1] / 'functions/facebook_fetch_new.py'
spec = importlib.util.spec_from_file_location('facebook_image_tests', MODULE)
fb = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'config': types.SimpleNamespace(DATA_DIR=Path('/unused'))}):
    with patch('builtins.open', mock_open(read_data='[]')):
        spec.loader.exec_module(fb)

URL = 'https://www.facebook.com/story.php?story_fbid=123&id=456'
POST_IMAGE = 'https://scontent.example/v/t39.30808-6/post.jpg'
COMMENT_IMAGE = 'https://scontent.example/v/t39.30808-6/comment.jpg?stp=cp6_s2048x2048'


def photo(uri, id='99'):
    return {'__typename': 'Photo', 'id': id, 'image': {'uri': uri}}


def story(attachments):
    return {'__typename': 'Story', 'id': 'story123', 'post_id': '123',
            'attachments': attachments,
            'feedback': {'comments': [{'__typename': 'Comment', 'attachments': [
                {'media': photo(COMMENT_IMAGE)}]}]}}


def html(root, og_image=None):
    meta = f'<meta property="og:image" content="{og_image}">' if og_image else ''
    data = json.dumps(root)
    return meta + f'<script type="application/json" data-content-len="{len(data)}" data-sjs>{data}</script>'


class ImageOwnershipTests(unittest.TestCase):
    def test_text_post_ignores_comments_recommendations_and_og(self):
        root = [dict(story([{'media': photo(COMMENT_IMAGE)}]), post_id='999', id='other'), story([])]
        page = html(root, COMMENT_IMAGE)
        anon = fb.parse_anonymous(page, URL)
        logged = fb.parse_logged_in(page, URL)
        self.assertIsNone(anon['image'])
        self.assertIsNone(logged['image'])
        self.assertIsNone(fb.merge_results(anon, logged)['image'])

    def test_post_photo_wins_over_larger_comment(self):
        page = html(story([{'styles': {'attachment': {'media': photo(POST_IMAGE)}}}]))
        for parse in (fb.parse_anonymous, fb.parse_logged_in):
            self.assertEqual(parse(page, URL)['image'], POST_IMAGE)

    def test_album(self):
        root = story([{'styles': {'attachment': {'all_subattachments': {
            'nodes': [{'media': photo(POST_IMAGE)}]}}}}])
        self.assertEqual(fb._extract_image_uri(root, URL), POST_IMAGE)

    def test_multiple_photos_preserve_order_and_deduplicate(self):
        second = POST_IMAGE.replace('post.jpg', 'second.jpg')
        attachments = [{'styles': {'attachment': {'all_subattachments': {
            'nodes': [{'media': photo(POST_IMAGE)}, {'media': photo(second, '100')},
                      {'media': photo(POST_IMAGE + '?size=small')}]
        }}}}]
        page = html(story(attachments))
        for parse in (fb.parse_anonymous, fb.parse_logged_in):
            data = parse(page, URL)
            self.assertEqual(data['images'], [POST_IMAGE, second])
            self.assertEqual(data['image'], POST_IMAGE)

    def test_merge_images_from_both_sessions(self):
        second = POST_IMAGE.replace('post.jpg', 'second.jpg')
        data = fb.merge_results({'images': [POST_IMAGE]},
                                {'images': [POST_IMAGE + '?signature=other', second]})
        self.assertEqual(data['images'], [POST_IMAGE, second])
        self.assertEqual(data['image'], POST_IMAGE)

    def test_fragment_same_story_id(self):
        root = [story([]), {'id': 'story123', 'attachments': [{'media': photo(POST_IMAGE)}]}]
        self.assertEqual(fb._extract_image_uri(root, URL), POST_IMAGE)

    def test_unknown_target_does_not_guess(self):
        self.assertIsNone(fb._extract_image_uri(story([{'media': photo(POST_IMAGE)}]),
                                                'https://www.facebook.com/share/p/unknown/'))

    def test_photo_fbid_is_not_story_fbid(self):
        root = [photo(COMMENT_IMAGE, '123'), photo(POST_IMAGE)]
        self.assertIsNone(fb._extract_image_by_fbid(root, URL))
        self.assertEqual(fb._extract_image_by_fbid(root, 'https://www.facebook.com/photo.php?fbid=99'), POST_IMAGE)

    def test_permalink_slug_and_canonical_url(self):
        root = story([{'media': photo(POST_IMAGE)}])
        root['permalink_url'] = 'https://www.facebook.com/user/posts/pfbidABC'
        self.assertEqual(fb._extract_image_uri(root, root['permalink_url']), POST_IMAGE)
        self.assertEqual(fb._extract_image_uri(root, 'https://www.facebook.com/user/posts/title/123/'), POST_IMAGE)

    def test_reel_thumbnail_preserved(self):
        page = html({'preferred_thumbnail': {'image': {'uri': POST_IMAGE}}}, POST_IMAGE)
        url = 'https://www.facebook.com/reel/123/'
        for parse in (fb.parse_anonymous, fb.parse_logged_in):
            self.assertEqual(parse(page, url)['image'], POST_IMAGE)


if __name__ == '__main__':
    unittest.main()

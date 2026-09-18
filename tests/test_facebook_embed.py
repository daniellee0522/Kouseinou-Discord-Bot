"""Execute the Facebook handler alone, without starting the bot or other cogs."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

import discord

source = Path(__file__).resolve().parents[1] / 'cmds/events.py'
tree = ast.parse(source.read_text())
handler = next(node for node in ast.walk(tree)
               if isinstance(node, ast.AsyncFunctionDef) and node.name == 'handler_facebook')


class FacebookEmbedTests(unittest.IsolatedAsyncioTestCase):
    async def run_handler(self, images):
        data = {'images': images, 'title': 'Example', 'post_text': 'Post text'}
        namespace = {'discord': discord, 'get_facebook_data': AsyncMock(return_value=data),
                     'is_embed_ban': Mock(return_value=False)}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), 'exec'), namespace)
        message = SimpleNamespace(guild=SimpleNamespace(id=123), channel=SimpleNamespace(send=AsyncMock()), edit=AsyncMock())
        await namespace['handler_facebook'](None, message, 'https://www.facebook.com/example/posts/123', None)
        message.channel.send.assert_awaited_once()
        message.edit.assert_awaited_once_with(suppress=True)
        return message.channel.send.call_args.kwargs

    async def test_only_first_four_images(self):
        images = [f'https://example.com/{i}.jpg' for i in range(7)]
        kwargs = await self.run_handler(images)
        embeds = kwargs['embeds']
        self.assertEqual([item.image.url for item in embeds], images[:4])
        self.assertEqual(len({item.url for item in embeds}), 1)
        self.assertEqual(embeds[0].description, 'Post text')
        self.assertTrue(all(item.description is None for item in embeds[1:]))

    async def test_text_only_post(self):
        kwargs = await self.run_handler([])
        self.assertIsNone(kwargs['embed'].image.url)

    async def test_single_image(self):
        kwargs = await self.run_handler(['https://example.com/one.jpg'])
        self.assertEqual(len(kwargs['embeds']), 1)

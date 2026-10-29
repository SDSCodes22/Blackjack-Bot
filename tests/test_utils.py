import json
import unittest
from io import BytesIO
from unittest.mock import mock_open, patch

from PIL import Image

import utils


class FakeResponse:
    def __init__(self, content):
        self.content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    def raise_for_status(self):
        return None

    async def read(self):
        return self.content


class FakeSession:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    def get(self, url):
        return self.response


class UtilityCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        utils.get_emoji.cache_clear()
        utils.get_average_avatar_color.cache_clear()

    async def asyncTearDown(self):
        utils.get_emoji.cache_clear()
        utils.get_average_avatar_color.cache_clear()

    def test_get_emoji_caches_config_file_lookup(self):
        config = json.dumps({"bj_emojis": {"HeartsA": "<:ace:123>"}})
        with patch("builtins.open", mock_open(read_data=config)) as open_file:
            first = utils.get_emoji("HeartsA")
            second = utils.get_emoji("HeartsA")

        self.assertEqual(first, "<:ace:123>")
        self.assertEqual(second, first)
        open_file.assert_called_once_with("config.json", "r")

    async def test_avatar_color_fetches_and_processes_a_url_only_once(self):
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), (255, 0, 0)).save(image_buffer, format="PNG")
        response = FakeResponse(image_buffer.getvalue())
        session = FakeSession(response)
        url = "https://example.test/avatar-cache-test.png"

        with patch.object(utils.aiohttp, "ClientSession", return_value=session) as client_session:
            first = await utils.get_average_avatar_color(url)
            second = await utils.get_average_avatar_color(url)

        self.assertEqual(first, 0xFF0000)
        self.assertEqual(second, first)
        client_session.assert_called_once()


if __name__ == "__main__":
    unittest.main()

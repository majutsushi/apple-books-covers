# noqa: INP001

import os
import sys
import typing
import unittest
from queue import Queue
from threading import Event

test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [test_dir, *sys.path]

from calibre.utils.logging import default_log  # noqa: E402

if typing.TYPE_CHECKING:
    from .. import AppleBooksCovers
else:
    from calibre_plugins.applebooks_covers import AppleBooksCovers


class TestAppleBooksCovers(unittest.TestCase):
    def setUp(self):
        self.plugin = AppleBooksCovers(None)
        self.plugin.log = default_log  # type: ignore[reportAttributeAccessIssue]
        self.queue = Queue()

    def test_isbn_lookup(self):
        max_covers = 5
        self.plugin.prefs[self.plugin.KEY_MAX_COVERS] = max_covers
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = None

        self.plugin.download_cover(
            default_log,
            self.queue,
            Event(),
            title="The Fifth Witness",
            authors=("Michael Connelly",),
            identifiers={"isbn": "9780316069359"},
        )
        self.assertGreaterEqual(self.queue.qsize(), 1)
        self.assertLessEqual(self.queue.qsize(), max_covers)

    def test_search(self):
        max_covers = 5
        self.plugin.prefs[self.plugin.KEY_MAX_COVERS] = max_covers
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = None

        self.plugin.download_cover(
            default_log,
            self.queue,
            Event(),
            title="A Game of Thrones",
            authors=("George R. R. Martin",),
        )
        self.assertEqual(self.queue.qsize(), max_covers)

    def test_multi_store(self):
        max_covers = 2
        self.plugin.prefs[self.plugin.KEY_MAX_COVERS] = max_covers
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = "GB"

        self.plugin.download_cover(
            default_log,
            self.queue,
            Event(),
            title="Dark in Death",
            authors=("J. D. Robb",),
        )
        self.assertEqual(self.queue.qsize(), max_covers)


if __name__ == "__main__":
    unittest.main(module="test_applebooks", verbosity=2)

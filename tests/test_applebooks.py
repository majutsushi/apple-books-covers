# noqa: INP001
# pyright: reportPrivateUsage=false

import os
import sys
import typing
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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

    def assertRequest(self, url: str) -> None:
        req = Request(url, method="HEAD")  # noqa: S310
        try:
            urlopen(req)  # noqa: S310
        except HTTPError:
            self.fail(f"URL failed: {url}")

    def test_isbn_lookup(self):
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = None

        results = self.plugin._find_covers(
            default_log,
            title="The Fifth Witness",
            authors=("Michael Connelly",),
            identifiers={"isbn": "9780316069359"},
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].author, "Michael Connelly")
        self.assertEqual(results[0].title, "The Fifth Witness")
        self.assertRequest(results[0].artwork_url)

    def test_search(self):
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = None

        results = self.plugin._find_covers(
            default_log,
            title="A Game of Thrones",
            authors=("George R. R. Martin",),
        )
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].author, "George R.R. Martin")
        self.assertEqual(results[0].title, "A Game of Thrones")
        self.assertIn("George R.R. Martin", results[1].author)
        self.assertIn("A Game of Thrones", results[1].title)
        self.assertRequest(results[0].artwork_url)

    def test_search2(self):
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = None

        results = self.plugin._find_covers(
            default_log,
            title="The Fifth Season",
            authors=("N. K. Jemisin",),
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].author, "N. K. Jemisin")
        self.assertEqual(results[0].title, "The Fifth Season")
        self.assertRequest(results[0].artwork_url)

    def test_search_multi_author(self):
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = None

        results = self.plugin._find_covers(
            default_log,
            title="The Three-Body Problem",
            authors=("Cixin Liu", "Ken Liu"),
        )
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].author, "Cixin Liu & Ken Liu")
        self.assertEqual(results[0].title, "The Three-Body Problem")
        self.assertEqual(results[1].author, "Cixin Liu, Ken Liu & Joel Martinsen")
        self.assertEqual(results[1].title, "The Three-Body Problem Series")
        self.assertRequest(results[0].artwork_url)
        self.assertRequest(results[1].artwork_url)

    def test_multi_store(self):
        self.plugin.prefs[self.plugin.KEY_COUNTRY] = "US"
        self.plugin.prefs[self.plugin.KEY_ADDITIONAL_COUNTRY] = "GB"

        results = self.plugin._find_covers(
            default_log,
            title="Dark in Death",
            authors=("J. D. Robb",),
        )
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].author, "J. D. Robb")
        self.assertEqual(results[0].title, "Dark in Death")
        self.assertEqual(results[1].author, "J. D. Robb")
        self.assertEqual(results[1].title, "Dark in Death")
        self.assertRequest(results[0].artwork_url)
        self.assertRequest(results[1].artwork_url)


if __name__ == "__main__":
    unittest.main(module="test_applebooks", verbosity=2)

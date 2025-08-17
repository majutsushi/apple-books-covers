# https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/index.html
# https://bendodson.com/projects/itunes-artwork-finder/
# https://github.com/lbschenkel/calibre-amazon-hires-covers

from __future__ import annotations

import json
import pprint
from dataclasses import dataclass
from itertools import cycle, islice
from typing import TYPE_CHECKING, Any, Generator, Iterable, TypeVar, cast
from urllib.parse import urlencode, urljoin

from calibre.ebooks.metadata.sources.base import Option, Source

if TYPE_CHECKING:
    from queue import Queue
    from threading import Event

    from calibre.utils.browser import Browser
    from calibre.utils.logging import Log

BASE_URL_LOOKUP = "https://itunes.apple.com/lookup?"
BASE_URL_SEARCH = "https://itunes.apple.com/search?"


@dataclass(frozen=True)
class Result:
    author: str
    title: str
    artwork_url: str

    @classmethod
    def from_dict(cls, result: dict[str, Any]) -> Result:
        image = "100000x100000-999.jpg"
        artwork_url = urljoin(result["artworkUrl100"], image)
        return cls(result["artistName"], result["trackName"], artwork_url)

    def __eq__(self, value: object, /) -> bool:
        if isinstance(value, Result):
            return self.artwork_url == value.artwork_url
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.artwork_url)


def load_countries():
    data = json.loads(get_resources("iso_3166-1.json"))
    return {item["alpha_2"]: item["name"] for item in data["3166-1"]}


class AppleBooksCovers(Source):
    name = "Apple Books covers"
    description = "Downloads high resolution covers from the Apple Books store"
    capabilities = frozenset(["cover"])
    author = "Jan Larres"
    version = (1, 0, 0)
    can_get_multiple_covers = True

    _countries = load_countries()

    KEY_MAX_COVERS = "max_covers"
    KEY_COUNTRY = "country"
    KEY_ADDITIONAL_COUNTRY = "additional_country"

    options = (
        Option(
            KEY_MAX_COVERS,
            "number",
            5,
            _("Maximum number of covers to get"),
            _(
                "The maximum number of covers to get from Apple Books."
                " Higher numbers may lead to slower response times."
                " Note that this is per country, so if you have an additional"
                " country configured there may be up to twice as many covers returned."
            ),
        ),
        Option(
            KEY_COUNTRY,
            "choices",
            "US",
            _("Store country to use"),
            _("Store country to use"),
            _countries,
        ),
        Option(
            KEY_ADDITIONAL_COUNTRY,
            "choices",
            None,
            _("Additional store country to use"),
            _(
                "An additional store to search for results and merge them with any previous ones."
                " Note that this might lead to hitting the rate limit more quickly."
            ),
            {None: "(Disabled)", **_countries},
        ),
    )

    def download_cover(
        self,
        log: Log,
        result_queue: Queue[tuple[AppleBooksCovers, bytes]],
        abort: Event,
        title: str | None = None,
        authors: tuple[str, ...] | None = None,
        identifiers: dict[str, str] | None = None,
        timeout: int = 30,
        get_best_cover: bool = False,
    ):
        results = self._find_covers(log, title, authors, identifiers)
        urls = [result.artwork_url for result in results]

        if urls:
            self.download_multiple_covers(
                title,
                authors,
                urls,
                get_best_cover,
                timeout,
                result_queue,
                abort,
                log,
                self.KEY_MAX_COVERS,
            )

    def _find_covers(
        self,
        log: Log,
        title: str | None = None,
        authors: tuple[str, ...] | None = None,
        identifiers: dict[str, str] | None = None,
    ):
        if identifiers is None:
            identifiers = {}

        title_tokens = list(self.get_title_tokens(title, strip_subtitle=True))
        author_tokens = list(self.get_author_tokens(authors, only_first_author=True))

        base_params = {
            "entity": "ebook",
            "limit": max(10, int(self.prefs[self.KEY_MAX_COVERS])),
            "version": "2",
        }
        country = cast("str", self.prefs[self.KEY_COUNTRY])
        country2 = cast("str | None", self.prefs[self.KEY_ADDITIONAL_COUNTRY])

        results: list[Result] = []

        # Try looking up the ISBN first
        if "isbn" in identifiers:
            lookup_params = {"isbn": identifiers["isbn"], **base_params}
            isbn_results = lookup(
                {**lookup_params, "country": country}, self.browser, log
            )
            if isbn_results:
                results.extend(isbn_results)
            elif country2 is not None:
                isbn_results = lookup(
                    {**lookup_params, "country": country2},
                    self.browser,
                    log,
                )
                if isbn_results:
                    results.extend(isbn_results)

        # Now do a search
        search_results = [
            search(
                author_tokens,
                title_tokens,
                {**base_params, "country": country},
                self.browser,
                log,
            )
        ]
        if country2 is not None:
            search_results.append(
                search(
                    author_tokens,
                    title_tokens,
                    {**base_params, "country": country2},
                    self.browser,
                    log,
                )
            )
        # Since later results are going to be less relevant,
        # we want to prioritize the earlier results from both searches
        results.extend(roundrobin(*search_results))

        # Remove duplicates while preserving order
        results = list(dict.fromkeys(results))
        log.info(f"Found results: {pprint.pformat(results)}")

        return results


def get_url_json(browser: Browser, url: str) -> dict[str, Any]:
    r = browser.open(url)
    if r is None:
        return {}
    return json.loads(r.read().decode("utf-8"))


def lookup(params: dict[str, Any], browser: Browser, log: Log) -> list[Result]:
    url = BASE_URL_LOOKUP + urlencode(params)
    log.info("Lookup URL: " + url)
    results = get_url_json(browser, url)
    return [Result.from_dict(result) for result in results.get("results", [])]


def search(
    author_tokens: list[str],
    title_tokens: list[str],
    params: dict[str, Any],
    browser: Browser,
    log: Log,
) -> list[Result]:
    results = do_query({**params, "term": " ".join(title_tokens)}, browser, log)
    filtered = filter_results(results, author_tokens, title_tokens)
    if filtered:
        return filtered

    # Try again by searching for both the title and the author,
    # which may be useful for very generic titles
    results = do_query(
        {**params, "term": f"{' '.join(title_tokens)} {' '.join(author_tokens)}"},
        browser,
        log,
    )
    return filter_results(results, author_tokens, title_tokens)


def do_query(params: dict[str, Any], browser: Browser, log: Log) -> list[Result]:
    url = BASE_URL_SEARCH + urlencode(params)
    log.info("Search URL: " + url)
    results = get_url_json(browser, url)
    return [Result.from_dict(result) for result in results.get("results", [])]


def filter_results(
    results: list[Result], author_tokens: list[str], title_tokens: list[str]
) -> list[Result]:
    return [
        result
        for result in results
        if all(token in result.title for token in title_tokens)
        and all(token in result.author for token in author_tokens)
    ]


T = TypeVar("T")


def roundrobin(*iterables: Iterable[T]) -> Generator[T, None, None]:
    "Visit input iterables in a cycle until each is exhausted."
    # roundrobin('ABC', 'D', 'EF') → A D E B F C
    # Algorithm credited to George Sakkis
    iterators = map(iter, iterables)
    for num_active in range(len(iterables), 0, -1):
        iterators = cycle(islice(iterators, num_active))
        yield from map(next, iterators)

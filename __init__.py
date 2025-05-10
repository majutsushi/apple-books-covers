# https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/index.html
# https://bendodson.com/projects/itunes-artwork-finder/
# https://github.com/lbschenkel/calibre-amazon-hires-covers

import json
from itertools import cycle, islice
from urllib.parse import urlencode, urljoin

from calibre.ebooks.metadata.sources.base import Option, Source

BASE_URL_LOOKUP = "https://itunes.apple.com/lookup?"
BASE_URL_SEARCH = "https://itunes.apple.com/search?"


def load_countries():
    data = json.loads(get_resources("iso_3166-1.json"))
    return {item["alpha_2"]: item["name"] for item in data["3166-1"]}


class AppleBooksCovers(Source):
    name = "Apple Books covers"
    description = "Downloads high resolution covers from the Apple Books store"
    capabilities = frozenset(["cover"])
    author = "Jan Larres"
    version = (0, 2, 0)
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
        log,
        result_queue,
        abort,
        title=None,
        authors=None,
        identifiers=None,
        timeout=30,
        get_best_cover=False,
    ):
        if identifiers is None:
            identifiers = {}

        title = " ".join(self.get_title_tokens(title))
        author = " ".join(self.get_author_tokens(authors))
        urls = self.get_cover_urls(log, title, author, identifiers)
        log.info("Cover URLs: " + repr(urls))

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

    def get_cover_urls(self, log, title, author, identifiers):
        base_params = {
            "entity": "ebook",
            "limit": self.prefs[self.KEY_MAX_COVERS],
            "version": "2",
        }
        country = self.prefs[self.KEY_COUNTRY]
        country2 = self.prefs[self.KEY_ADDITIONAL_COUNTRY]

        results = []

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
        search_params = {"term": f"{author} {title}", **base_params}
        search_results = [
            search({**search_params, "country": country}, self.browser, log)
        ]
        if country2 is not None:
            search_results.append(
                search({**search_params, "country": country2}, self.browser, log)
            )
        # Since later results are going to be less relevant,
        # we want to prioritize the earlier results from both searches
        results.extend(roundrobin(*search_results))

        # Remove duplicates while preserving order
        return list(dict.fromkeys(self.get_full_cover_urls(results)))

    def get_full_cover_urls(self, results):
        image = "100000x100000-999.jpg"
        return [urljoin(result["artworkUrl100"], image) for result in results]


def get_url_json(browser, url):
    r = browser.open(url)
    if r is None:
        return {}
    return json.loads(r.read().decode("utf-8"))


def lookup(params, browser, log):
    url = BASE_URL_LOOKUP + urlencode(params)
    log.info("Lookup URL: " + url)
    results = get_url_json(browser, url)
    return results.get("results", [])


def search(params, browser, log):
    url = BASE_URL_SEARCH + urlencode(params)
    log.info("Search URL: " + url)
    results = get_url_json(browser, url)
    return results.get("results", [])


def roundrobin(*iterables):
    "Visit input iterables in a cycle until each is exhausted."
    # roundrobin('ABC', 'D', 'EF') → A D E B F C
    # Algorithm credited to George Sakkis
    iterators = map(iter, iterables)
    for num_active in range(len(iterables), 0, -1):
        iterators = cycle(islice(iterators, num_active))
        yield from map(next, iterators)

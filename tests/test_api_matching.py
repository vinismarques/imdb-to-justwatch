"""Title matching in JustWatchClient.get_title_id.

The HTTP boundary is faked; everything below get_title_id is free to change.
"""

from __future__ import annotations

import pytest

from imdb_justwatch_util import api
from imdb_justwatch_util.api import JustWatchClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def search_results(*titles: tuple[str, int, str]) -> dict:
    """Builds a popularTitles payload from (title, year, id) triples."""
    return {
        "data": {
            "popularTitles": {
                "edges": [
                    {
                        "node": {
                            "id": title_id,
                            "objectType": "MOVIE",
                            "content": {"title": title, "originalReleaseYear": year},
                        }
                    }
                    for title, year, title_id in titles
                ]
            }
        }
    }


@pytest.fixture
def fake_search(monkeypatch):
    """Serves canned results per request, and records the year windows requested."""

    def _install(responder):
        windows = []

        def fake_post(url: str, headers: dict, json: dict) -> FakeResponse:
            search_filter = json["variables"].get("searchTitlesFilter", {})
            windows.append(search_filter.get("releaseYear"))
            return FakeResponse(responder(search_filter))

        monkeypatch.setattr(api.requests, "post", fake_post)
        return windows

    return _install


@pytest.fixture
def client(monkeypatch) -> JustWatchClient:
    monkeypatch.setenv("JUSTWATCH_AUTH_TOKEN", "test-token")
    return JustWatchClient(country="US", language="en-US")


def test_unrelated_result_is_rejected(client, fake_search) -> None:
    """JustWatch answers a miss with some other film from that year; it must not be accepted."""
    fake_search(lambda _filter: search_results(("New York, I Love You", 2008, "tm59966")))

    assert client.get_title_id("Synecdoche, New York", "MOVIE", 2008) is None


def test_title_is_found_when_justwatch_dates_it_a_year_later(client, fake_search) -> None:
    """IMDb says 2019, JustWatch says 2020; a near-miss title from 2019 must not win instead."""

    def responder(search_filter: dict) -> dict:
        window = search_filter.get("releaseYear")
        if window and window["min"] <= 2020 <= window["max"]:
            return search_results(("The Gentlemen", 2020, "tm441050"))
        return search_results(("The Gentle Men", 2019, "tm994491"))

    fake_search(responder)

    assert client.get_title_id("The Gentlemen", "MOVIE", 2019) == "tm441050"


def test_falls_back_to_a_wider_year_window(client, fake_search) -> None:
    """Some titles are dated a few years apart; the year must not be the reason we give up."""

    def responder(search_filter: dict) -> dict:
        window = search_filter["releaseYear"]
        if window["min"] <= 1999 <= window["max"]:
            return search_results(("Frailty", 1999, "tm58787"))
        return search_results()

    windows = fake_search(responder)

    assert client.get_title_id("Frailty", "MOVIE", 2001) == "tm58787"
    assert windows[-1] == {"min": 2001 - api.FALLBACK_YEAR_TOLERANCE, "max": 2001 + api.FALLBACK_YEAR_TOLERANCE}


def test_the_widened_window_still_rejects_a_distant_year(client, fake_search) -> None:
    """Dropping the year entirely matched 'The Wave' (2008) to an unrelated 2015 film."""

    def responder(search_filter: dict) -> dict:
        window = search_filter["releaseYear"]
        if window["min"] <= 2015 <= window["max"]:
            return search_results(("The Wave", 2015, "tm207546"))
        return search_results()

    fake_search(responder)

    assert client.get_title_id("The Wave", "MOVIE", 2008) is None


def test_exact_title_wins_over_a_more_popular_near_miss(client, fake_search) -> None:
    """'The Gentle Men' outranks 'The Gentlemen' by popularity, but is a different film."""
    fake_search(
        lambda _filter: search_results(
            ("The Gentle Men", 2019, "tm994491"),
            ("The Gentlemen", 2020, "tm441050"),
        )
    )

    assert client.get_title_id("The Gentlemen", "MOVIE", 2019) == "tm441050"


def test_punctuation_and_numeral_variants_still_match(client, fake_search) -> None:
    fake_search(lambda _filter: search_results(("The Fantastic 4: First Steps", 2025, "tm839627")))

    assert client.get_title_id("The Fantastic Four: First Steps", "MOVIE", 2025) == "tm839627"


def test_failed_request_returns_none(client, monkeypatch) -> None:
    monkeypatch.setattr(api.JustWatchClient, "_make_request", lambda self, query, variables: None)

    assert client.get_title_id("Anything", "MOVIE", 2001) is None


def test_original_title_is_accepted(client, fake_search) -> None:
    """JustWatch answers with the original title where IMDb carries the English one."""
    fake_search(lambda _filter: search_results(("Hauru no ugoku shiro", 2004, "tm14180")))

    found = client.get_title_id("Howl's Moving Castle", "MOVIE", 2004, original_title="Hauru no ugoku shiro")
    assert found == "tm14180"


def test_original_title_does_not_widen_the_net_to_a_different_film(client, fake_search) -> None:
    fake_search(lambda _filter: search_results(("Some Other Film", 2004, "tm999")))

    assert client.get_title_id("Howl's Moving Castle", "MOVIE", 2004, original_title="Hauru no ugoku shiro") is None

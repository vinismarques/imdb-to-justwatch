"""A 429 must never be reported as a title JustWatch does not have."""

from __future__ import annotations

import csv

import pytest
import requests

import import_likelist
import import_seenlist
import import_watchlist
from imdb_justwatch_util import api
from imdb_justwatch_util.api import JustWatchClient, RateLimitedError

CSVS = {
    import_watchlist: "Const,Title,Title Type,Year\ntt1,A Movie,Movie,2001\ntt2,B Movie,Movie,2002\n",
    import_seenlist: "Const,Your Rating,Title,Title Type,Year\ntt1,9,A Movie,Movie,2001\ntt2,9,B Movie,Movie,2002\n",
    import_likelist: "Const,Your Rating,Title,Title Type,Year\ntt1,9,A Movie,Movie,2001\ntt2,9,B Movie,Movie,2002\n",
}


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, headers: dict | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def client(monkeypatch) -> JustWatchClient:
    monkeypatch.setenv("JUSTWATCH_AUTH_TOKEN", "test-token")
    return JustWatchClient(country="US", language="en-US")


@pytest.fixture
def waits(monkeypatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(api, "sleep", recorded.append)
    return recorded


def serve(monkeypatch, responses: list[FakeResponse]) -> None:
    queue = list(responses)
    monkeypatch.setattr(api.requests, "post", lambda *a, **k: queue.pop(0))


def test_a_throttled_request_is_retried(client, monkeypatch, waits) -> None:
    serve(monkeypatch, [FakeResponse(429), FakeResponse(200, {"data": {"ok": True}})])

    assert client._make_request("query", {}) == {"data": {"ok": True}}
    assert waits == [api.RATE_LIMIT_BACKOFF_SECONDS]


def test_retry_after_header_is_honoured(client, monkeypatch, waits) -> None:
    serve(monkeypatch, [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, {"data": {}})])

    client._make_request("query", {})

    assert waits == [7.0]


def test_backoff_grows_between_attempts(client, monkeypatch, waits) -> None:
    serve(monkeypatch, [FakeResponse(429)] * api.RATE_LIMIT_MAX_ATTEMPTS)

    with pytest.raises(RateLimitedError):
        client._make_request("query", {})

    assert waits == [api.RATE_LIMIT_BACKOFF_SECONDS * 2**i for i in range(api.RATE_LIMIT_MAX_ATTEMPTS - 1)]


def test_sustained_throttling_is_not_a_missing_title(client, monkeypatch, waits) -> None:
    """get_title_id must not swallow the 429 into a None that reads as 'not on JustWatch'."""
    serve(monkeypatch, [FakeResponse(429)] * api.RATE_LIMIT_MAX_ATTEMPTS)

    with pytest.raises(RateLimitedError):
        client.get_title_id("A Movie", "MOVIE", 2001)


@pytest.mark.parametrize("module", list(CSVS))
def test_importers_report_throttling_and_stop(monkeypatch, write_csv, tmp_path, module) -> None:
    lookups = []

    class ThrottledClient:
        def get_title_id(self, title_name: str, title_type: str, release_year, original_title: str = "") -> str:
            lookups.append(title_name)
            msg = "JustWatch is rate limiting this run (429 after 3 attempts)."
            raise RateLimitedError(msg)

    monkeypatch.setattr(module, "JustWatchClient", lambda **kwargs: ThrottledClient())
    monkeypatch.setattr(module, "CSV_FILE_PATH", write_csv("input.csv", CSVS[module]))
    monkeypatch.setattr(module, "sleep", lambda seconds: None)
    monkeypatch.chdir(tmp_path)

    module.main(False)

    assert lookups == ["A Movie"], "the run must stop rather than throttle every remaining title"
    report = next((tmp_path / "logs").glob("*-unmatched-*.csv"))
    rows = list(csv.DictReader(report.open(encoding="utf-8")))
    assert [r["Reason"] for r in rows] == ["rate_limited"]

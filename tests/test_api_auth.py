"""Token handling. Every value here comes from a real user report on the release thread."""

from __future__ import annotations

import pytest

from imdb_justwatch_util import api
from imdb_justwatch_util.api import JustWatchClient

TOKEN = "eyJhbGciOiJIUzI1NiJ9.payload.signature"


@pytest.mark.parametrize(
    "raw_token",
    [
        f'"Bearer {TOKEN}"',  # Windows CMD keeps the quotes in the value
        f"'Bearer {TOKEN}'",
        f"  Bearer {TOKEN}  ",
        f"Bearer {TOKEN}\n",
    ],
)
def test_stray_quotes_and_whitespace_are_stripped(monkeypatch, raw_token: str) -> None:
    monkeypatch.setenv("JUSTWATCH_AUTH_TOKEN", raw_token)

    client = JustWatchClient()

    assert client.headers["Authorization"] == f"Bearer {TOKEN}"


@pytest.fixture
def client(monkeypatch) -> JustWatchClient:
    monkeypatch.setenv("JUSTWATCH_AUTH_TOKEN", f"Bearer {TOKEN}")
    return JustWatchClient()


def test_unauthorized_response_raises_instead_of_failing_title_by_title(client, monkeypatch) -> None:
    """A rejected token fails every request; grinding through the whole CSV helps nobody."""

    class Unauthorized:
        status_code = 401
        content = b'{"error":"checking Firebase token: illegal base64 data at input byte 0"}'

        def raise_for_status(self) -> None:
            raise api.requests.exceptions.HTTPError("401 Client Error: Unauthorized", response=self)

    monkeypatch.setattr(api.requests, "post", lambda *args, **kwargs: Unauthorized())

    with pytest.raises(api.AuthenticationError):
        client.get_title_id("Memory", "MOVIE", 2022)

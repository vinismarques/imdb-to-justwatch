"""A rejected token must stop the run, not repeat for every row in the CSV."""

from __future__ import annotations

import pytest

import import_likelist
import import_seenlist
import import_watchlist
from imdb_justwatch_util import api

CSVS = {
    import_watchlist: "Const,Title,Title Type,Year\ntt1,A Movie,Movie,2001\ntt2,B Movie,Movie,2002\n",
    import_seenlist: "Const,Your Rating,Title,Title Type,Year\ntt1,9,A Movie,Movie,2001\ntt2,9,B Movie,Movie,2002\n",
    import_likelist: "Const,Your Rating,Title,Title Type,Year\ntt1,9,A Movie,Movie,2001\ntt2,9,B Movie,Movie,2002\n",
}


@pytest.mark.parametrize("module", list(CSVS))
def test_import_stops_after_the_first_rejected_request(monkeypatch, write_csv, module) -> None:
    lookups = []

    class RejectingClient:
        def get_title_id(self, title_name: str, title_type: str, release_year: int | None) -> str:
            lookups.append(title_name)
            msg = "JustWatch rejected JUSTWATCH_AUTH_TOKEN (401)."
            raise api.AuthenticationError(msg)

    monkeypatch.setattr(module, "JustWatchClient", lambda **kwargs: RejectingClient())
    monkeypatch.setattr(module, "CSV_FILE_PATH", write_csv("input.csv", CSVS[module]))
    monkeypatch.setattr(module, "sleep", lambda seconds: None)

    module.main(False)

    assert lookups == ["A Movie"], "the second title must never be attempted"

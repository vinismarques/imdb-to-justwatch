"""Behaviour shared by the watchlist and seenlist importers."""

from __future__ import annotations

import import_seenlist
import import_watchlist
import pytest

CASES = [
    (import_watchlist, "watchlist", "Const,Title,Title Type,Year\n"),
    (import_seenlist, "seenlist", "Const,Your Rating,Title,Title Type,Year\n"),
]


def rows(module, *titles: str) -> str:
    rating = "9," if module is import_seenlist else ""
    return "".join(f"tt{i},{rating}{title},Movie,200{i}\n" for i, title in enumerate(titles, start=1))


@pytest.mark.parametrize(("module", "action", "header"), CASES)
def test_titles_are_added(run_importer, module, action: str, header: str) -> None:
    client, _ = run_importer(module, header + rows(module, "A Movie"))

    assert client.calls == [(action, "tm_A_Movie")]


@pytest.mark.parametrize(("module", "action", "header"), CASES)
def test_dry_run_looks_up_but_does_not_mutate(run_importer, module, action: str, header: str) -> None:
    client, _ = run_importer(module, header + rows(module, "A Movie", "B Movie"), dry_run=True)

    assert client.lookups == ["A Movie", "B Movie"]
    assert client.calls == []


@pytest.mark.parametrize(("module", "action", "header"), CASES)
def test_missing_titles_are_skipped(run_importer, module, action: str, header: str) -> None:
    client, _ = run_importer(module, header + rows(module, "Ghost", "A Movie"), missing_titles={"Ghost"})

    assert client.calls == [(action, "tm_A_Movie")]


@pytest.mark.parametrize(("module", "action", "header"), CASES)
def test_unsupported_types_are_not_looked_up(run_importer, module, action: str, header: str) -> None:
    rating = "9," if module is import_seenlist else ""
    client, _ = run_importer(module, header + f"tt1,{rating}Some Game,Video Game,2001\n")

    assert client.lookups == []

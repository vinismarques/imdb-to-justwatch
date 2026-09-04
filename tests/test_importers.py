"""Behaviour shared by all three importers."""

from __future__ import annotations

import pytest

import import_likelist
import import_seenlist
import import_watchlist

RATINGS_HEADER = "Const,Your Rating,Title,Title Type,Year\n"

CASES = [
    (import_watchlist, "watchlist", "Const,Title,Title Type,Year\n"),
    (import_seenlist, "seenlist", RATINGS_HEADER),
]


def rows(module, *titles: str) -> str:
    rating = "" if module is import_watchlist else "9,"
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
    rating = "" if module is import_watchlist else "9,"
    client, _ = run_importer(module, header + f"tt1,{rating}Some Game,Video Game,2001\n")

    assert client.lookups == []


@pytest.mark.parametrize(("module", "action", "header"), CASES + [(import_likelist, "like", RATINGS_HEADER)])
def test_import_continues_after_an_unreadable_row(monkeypatch, run_importer, module, action: str, header: str) -> None:
    """A row that raises must be logged and skipped, not abort the import."""

    class ExplodingRow:
        def get(self, *args, **kwargs):
            raise RuntimeError("unreadable row")

    real_dictreader = module.csv.DictReader

    def dictreader_with_bad_first_row(f):
        reader = real_dictreader(f)
        rows = list(reader)

        class Reader:
            fieldnames = reader.fieldnames

            def __iter__(self):
                yield ExplodingRow()
                yield from rows

        return Reader()

    monkeypatch.setattr(module.csv, "DictReader", dictreader_with_bad_first_row)
    client, _ = run_importer(module, header + rows(module, "A Movie"))

    assert client.calls == [(action, "tm_A_Movie")]


@pytest.mark.parametrize(("module", "action", "header"), CASES + [(import_likelist, "like", RATINGS_HEADER)])
def test_titles_needing_attention_are_written_to_a_report(
    monkeypatch, tmp_path, run_importer, module, action: str, header: str
) -> None:
    """Skipped titles have to be re-entered by hand, so they need to outlive the terminal."""
    monkeypatch.chdir(tmp_path)

    run_importer(module, header + rows(module, "Ghost", "A Movie"), missing_titles={"Ghost"})

    reports = list((tmp_path / "logs").glob("*unmatched*.csv"))
    assert len(reports) == 1
    report = reports[0].read_text()
    assert "Ghost" in report
    assert "A Movie" not in report, "titles that imported cleanly do not need attention"

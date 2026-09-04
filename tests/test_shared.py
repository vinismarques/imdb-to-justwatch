from __future__ import annotations

import pytest
from imdb_justwatch_util.shared import map_imdb_type_to_justwatch, parse_dry_run


@pytest.mark.parametrize(
    ("imdb_type", "expected"),
    [
        ("Movie", "MOVIE"),
        ("tvMovie", "MOVIE"),
        ("Film", "MOVIE"),
        ("Series", "SHOW"),
        ("tvSeries", "SHOW"),
        ("miniSeries", "SHOW"),
        ("Video Game", None),
        ("", None),
    ],
)
def test_map_imdb_type_to_justwatch(imdb_type: str, expected: str | None) -> None:
    assert map_imdb_type_to_justwatch(imdb_type) == expected


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["import_likelist.py"], False),
        (["import_likelist.py", "--dry-run"], True),
    ],
)
def test_parse_dry_run(monkeypatch, argv: list[str], expected: bool) -> None:
    monkeypatch.setattr("sys.argv", argv)
    assert parse_dry_run("test") is expected


def test_parse_dry_run_rejects_unknown_arguments(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["import_likelist.py", "exports/other.csv"])
    with pytest.raises(SystemExit):
        parse_dry_run("test")

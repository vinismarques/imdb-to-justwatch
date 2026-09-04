from __future__ import annotations

import csv

import pytest

from imdb_justwatch_util import shared
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


def test_utf8_export_is_decoded(tmp_path) -> None:
    path = tmp_path / "ratings.csv"
    path.write_bytes("Title\nShōgun\n".encode())

    assert list(csv.DictReader(shared.open_imdb_export(path))) == [{"Title": "Shōgun"}]


def test_utf8_bom_is_stripped(tmp_path) -> None:
    """A BOM left in the first header name stops 'Title' from being found at all."""
    path = tmp_path / "ratings.csv"
    path.write_bytes("Title\nShōgun\n".encode("utf-8-sig"))

    assert list(csv.DictReader(shared.open_imdb_export(path))) == [{"Title": "Shōgun"}]


def test_non_utf8_export_falls_back(tmp_path) -> None:
    path = tmp_path / "ratings.csv"
    path.write_bytes("Title\nAmélie\n".encode("cp1252"))

    assert list(csv.DictReader(shared.open_imdb_export(path))) == [{"Title": "Amélie"}]

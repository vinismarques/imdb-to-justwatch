from __future__ import annotations

import pytest

import import_likelist
from import_likelist import process_likelist_entry

HEADER = "Const,Your Rating,Title,Title Type,Year\n"


def outcome(client, rating: str, *, title: str = "A Movie", imdb_type: str = "Movie", dry_run: bool = False) -> str:
    return process_likelist_entry(client, title, imdb_type, "2001", rating, dry_run)


@pytest.mark.parametrize(
    ("rating", "expected"),
    [
        ("10", "liked"),
        ("7", "liked"),  # LIKE_MIN_RATING
        ("6", "neutral"),
        ("5", "neutral"),
        ("4", "disliked"),  # DISLIKE_MAX_RATING
        ("1", "disliked"),
    ],
)
def test_rating_thresholds(client, rating: str, expected: str) -> None:
    assert outcome(client, rating) == expected


@pytest.mark.parametrize("rating", ["", "  ", "N/A"])
def test_unusable_ratings_are_skipped_without_lookup(client, rating: str) -> None:
    assert outcome(client, rating.strip()) in {"unrated", "invalid_rating"}
    assert client.lookups == []


def test_neutral_rating_is_skipped_without_lookup(client) -> None:
    assert outcome(client, "5") == "neutral"
    assert client.lookups == []


def test_unsupported_type_is_skipped_without_lookup(client) -> None:
    assert outcome(client, "9", imdb_type="Video Game") == "unsupported_type"
    assert client.lookups == []


def test_missing_title_reports_not_found(client) -> None:
    client.missing_titles = {"A Movie"}
    assert outcome(client, "9") == "not_found"
    assert client.calls == []


def test_failed_mutation_is_reported(client) -> None:
    client.mutations_succeed = False
    assert outcome(client, "9") == "failed"


def test_missing_year_still_looks_up_the_title(client) -> None:
    assert process_likelist_entry(client, "A Movie", "Movie", "", "9", False) == "liked"
    assert client.lookups == ["A Movie"]


@pytest.mark.parametrize(
    ("rating", "expected"),
    [("9", "would_like"), ("2", "would_dislike")],
)
def test_dry_run_looks_up_but_does_not_mutate(client, rating: str, expected: str) -> None:
    assert outcome(client, rating, dry_run=True) == expected
    assert client.lookups == ["A Movie"]
    assert client.calls == []


def test_main_only_paces_rows_that_reached_the_api(run_importer) -> None:
    csv_text = HEADER + (
        "tt1,9,Liked Movie,Movie,2001\n"
        "tt2,6,Neutral Movie,Movie,2002\n"
        "tt3,,Unrated Movie,Movie,2003\n"
        "tt4,9,Game,Video Game,2004\n"
    )
    client, sleep_calls = run_importer(import_likelist, csv_text)

    assert client.calls == [("like", "tm_Liked_Movie")]
    assert len(sleep_calls) == 1


def test_main_dry_run_sends_no_mutations(run_importer) -> None:
    csv_text = HEADER + "tt1,9,Liked Movie,Movie,2001\ntt2,2,Disliked Movie,Movie,2002\n"
    client, _ = run_importer(import_likelist, csv_text, dry_run=True)

    assert client.lookups == ["Liked Movie", "Disliked Movie"]
    assert client.calls == []


def test_main_skips_rows_without_a_title(run_importer) -> None:
    csv_text = HEADER + "tt1,9,,Movie,2001\ntt2,9,Liked Movie,Movie,2002\n"
    client, _ = run_importer(import_likelist, csv_text)

    assert client.lookups == ["Liked Movie"]


def test_main_reports_missing_columns_without_processing(run_importer) -> None:
    client, _ = run_importer(import_likelist, "Const,Title,Title Type,Year\ntt1,A Movie,Movie,2001\n")

    assert client.lookups == []

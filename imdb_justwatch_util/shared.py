from __future__ import annotations

import argparse

from loguru import logger

# --- Configuration ---
DEFAULT_COUNTRY = "US"
DEFAULT_LANGUAGE = "en-US"
REQUEST_DELAY_SECONDS = 1


def parse_dry_run(description: str) -> bool:
    """Returns whether the importer was invoked with --dry-run."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Look up every title on JustWatch and report what would change, without touching your account.",
    )
    return parser.parse_args().dry_run


def map_imdb_type_to_justwatch(imdb_type_str: str) -> str | None:
    """Converts IMDb title type string to JustWatch objectType."""
    # Checking for keywords is generally better.
    if "Movie" in imdb_type_str:  # Catches "Movie", "tvMovie"
        return "MOVIE"
    if "Film" in imdb_type_str:  # Catches "Film"
        return "MOVIE"
    if "Series" in imdb_type_str:  # Catches "Series", "tvSeries", "miniSeries"
        return "SHOW"
    logger.warning(f"Unsupported IMDb title type: '{imdb_type_str}'. Skipping.")
    return None

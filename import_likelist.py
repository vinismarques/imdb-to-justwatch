from __future__ import annotations

import csv
import os
import sys
from time import sleep

from dotenv import load_dotenv
from imdb_justwatch_util.api import JustWatchClient
from imdb_justwatch_util.shared import (
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    REQUEST_DELAY_SECONDS,
    map_imdb_type_to_justwatch,
)
from loguru import logger

load_dotenv()

# Reads exports/ratings.csv — the same file the seenlist import uses, but this
# script additionally requires a 'Your Rating' column (1-10). Rows with an empty
# rating are skipped (neither liked nor disliked).
# Override the path with a command-line argument, e.g.:
#   uv run python import_likelist.py exports/ratings_missing.csv
DEFAULT_CSV_FILE_PATH = os.path.join("exports", "ratings.csv")
CSV_FILE_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV_FILE_PATH

# --- Column Names from the IMDb ratings export ---
IMDB_TITLE_COLUMN = "Title"
IMDB_TYPE_COLUMN = "Title Type"
IMDB_YEAR_COLUMN = "Year"
IMDB_RATING_COLUMN = "Your Rating"

# --- Rating -> action thresholds (IMDb scale is 1-10) ---
LIKE_MIN_RATING = 7  # >= this -> thumbs up
DISLIKE_MAX_RATING = 4  # <= this -> thumbs down (needs setInDislikelist, see below)


def process_likelist_entry(
    client: JustWatchClient, imdb_title: str, imdb_type: str, imdb_year: str, imdb_rating: str
) -> None:
    """Processes a single IMDb ratings row: likes/dislikes based on the rating."""
    if not imdb_rating:
        logger.debug(f"No rating for '{imdb_title}'. Skipping.")
        return

    try:
        rating = int(imdb_rating)
    except ValueError:
        logger.warning(f"Invalid rating '{imdb_rating}' for '{imdb_title}'. Skipping.")
        return

    if rating >= LIKE_MIN_RATING:
        action = "like"
    elif rating <= DISLIKE_MAX_RATING:
        action = "dislike"
    else:
        logger.info(f"Rating {rating} for '{imdb_title}' is neutral ({DISLIKE_MAX_RATING + 1}-{LIKE_MIN_RATING - 1}). Skipping.")
        return

    logger.info(f"Processing for likelist: Title='{imdb_title}', Year='{imdb_year}', Rating={rating} -> {action}")

    justwatch_type = map_imdb_type_to_justwatch(imdb_type)
    if not justwatch_type:
        return

    try:
        year_int: int | None = int(imdb_year)
    except ValueError:
        logger.warning(f"Invalid year format '{imdb_year}' for title '{imdb_title}'. Attempting search without year.")
        year_int = None

    justwatch_id = client.get_title_id(title_name=imdb_title, title_type=justwatch_type, release_year=year_int)
    if not justwatch_id:
        logger.warning(f"Could not find '{imdb_title}' on JustWatch for likelist. Skipping.")
        return

    if action == "like":
        if client.add_to_likelist(justwatch_id):
            logger.success(f"Successfully liked '{imdb_title}' (ID: {justwatch_id}).")
        else:
            logger.error(f"Failed to like '{imdb_title}' (ID: {justwatch_id}).")
    else:  # dislike
        if client.add_to_dislikelist(justwatch_id):
            logger.success(f"Successfully disliked '{imdb_title}' (ID: {justwatch_id}).")
        else:
            logger.error(f"Failed to dislike '{imdb_title}' (ID: {justwatch_id}).")


def main() -> None:
    logger.info("Starting IMDb ratings import to JustWatch likelist...")

    if not os.path.exists(CSV_FILE_PATH):
        logger.error(f"CSV file not found at '{CSV_FILE_PATH}'. Please ensure it exists.")
        logger.info("This script needs an IMDb ratings export that INCLUDES the 'Your Rating' column.")
        return

    try:
        client = JustWatchClient(country=DEFAULT_COUNTRY, language=DEFAULT_LANGUAGE)
    except ValueError as e:
        logger.critical(f"Failed to initialize JustWatch client: {e}")
        logger.critical("Ensure the JUSTWATCH_AUTH_TOKEN environment variable is set correctly.")
        return

    logger.info(f"Reading ratings items from: {CSV_FILE_PATH}")
    entries_processed = 0

    try:
        with open(CSV_FILE_PATH, encoding="ISO-8859-1", newline="") as f:
            csv_reader = csv.DictReader(f)

            header = csv_reader.fieldnames
            if not header:
                logger.error(f"CSV file at '{CSV_FILE_PATH}' appears to be empty or has no header.")
                return

            required_columns = [IMDB_TITLE_COLUMN, IMDB_TYPE_COLUMN, IMDB_YEAR_COLUMN, IMDB_RATING_COLUMN]
            missing_columns = [col for col in required_columns if col not in header]
            if missing_columns:
                logger.error(f"Missing required columns in '{CSV_FILE_PATH}': {', '.join(missing_columns)}")
                logger.error(f"Available columns: {', '.join(header)}")
                logger.info("This script needs the full IMDb ratings export (with 'Your Rating').")
                return

            for i, row in enumerate(csv_reader):
                row_num_for_logging = i + 2
                logger.debug(f"Reading row {row_num_for_logging}: {row}")
                try:
                    imdb_title = row.get(IMDB_TITLE_COLUMN, "").strip()
                    imdb_type_str = row.get(IMDB_TYPE_COLUMN, "").strip()
                    imdb_year_str = row.get(IMDB_YEAR_COLUMN, "").strip()
                    imdb_rating_str = row.get(IMDB_RATING_COLUMN, "").strip()

                    if not imdb_title:
                        logger.warning(f"Skipping row {row_num_for_logging} due to empty title.")
                        continue

                    process_likelist_entry(client, imdb_title, imdb_type_str, imdb_year_str, imdb_rating_str)
                    entries_processed += 1

                except Exception:
                    logger.exception(
                        f"An unexpected error occurred processing row {row_num_for_logging} ('{imdb_title or 'N/A'}')."
                    )
                    continue

                logger.info(f"Waiting for {REQUEST_DELAY_SECONDS}s before next entry...")
                sleep(REQUEST_DELAY_SECONDS)

    except FileNotFoundError:
        logger.error(f"CSV file not found at '{CSV_FILE_PATH}'.")
        return
    except Exception as e:
        logger.critical(f"An unexpected error occurred during CSV processing: {e}")
        return

    logger.info("--- Import Summary ---")
    logger.info(f"Total entries processed from CSV for likelist: {entries_processed}")
    logger.success("IMDb ratings import to JustWatch likelist finished.")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    main()

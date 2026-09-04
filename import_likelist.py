from __future__ import annotations

import csv
import os
from collections import Counter
from time import sleep

from dotenv import load_dotenv
from loguru import logger

from imdb_justwatch_util.api import JustWatchClient
from imdb_justwatch_util.shared import (
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    REQUEST_DELAY_SECONDS,
    configure_logging,
    map_imdb_type_to_justwatch,
    parse_dry_run,
)

load_dotenv()

CSV_FILE_PATH = os.path.join("exports", "ratings.csv")  # Path to the IMDb ratings CSV

# --- Column Names from ratings.csv ---
# These are the actual header names we expect in the CSV for the relevant data.
IMDB_TITLE_COLUMN = "Title"
IMDB_TYPE_COLUMN = "Title Type"
IMDB_YEAR_COLUMN = "Year"
IMDB_RATING_COLUMN = "Your Rating"

# --- Rating -> action thresholds (IMDb scale is 1-10) ---
LIKE_MIN_RATING = 7
DISLIKE_MAX_RATING = 4

# Outcomes that reached the JustWatch API, and so must be followed by a delay.
NETWORK_OUTCOMES = frozenset({"liked", "disliked", "would_like", "would_dislike", "not_found", "failed"})


def process_likelist_entry(
    client: JustWatchClient, imdb_title: str, imdb_type: str, imdb_year: str, imdb_rating: str, dry_run: bool
) -> str:
    """Likes or dislikes a single ratings CSV entry. Returns an outcome key for the run summary."""
    if not imdb_rating:
        logger.debug(f"No rating for '{imdb_title}'. Skipping.")
        return "unrated"

    try:
        rating = int(imdb_rating)
    except ValueError:
        logger.warning(f"Invalid rating '{imdb_rating}' for '{imdb_title}'. Skipping.")
        return "invalid_rating"

    if rating >= LIKE_MIN_RATING:
        action = "like"
    elif rating <= DISLIKE_MAX_RATING:
        action = "dislike"
    else:
        logger.info(f"Rating {rating} for '{imdb_title}' is neutral. Skipping.")
        return "neutral"

    logger.info(f"Processing for likelist: Title='{imdb_title}', Year='{imdb_year}', Rating={rating} -> {action}")

    justwatch_type = map_imdb_type_to_justwatch(imdb_type)
    if not justwatch_type:
        return "unsupported_type"

    try:
        year_int = int(imdb_year)
    except ValueError:
        logger.warning(f"Invalid year format '{imdb_year}' for title '{imdb_title}'. Attempting search without year.")
        year_int = None

    justwatch_id = client.get_title_id(title_name=imdb_title, title_type=justwatch_type, release_year=year_int)
    if not justwatch_id:
        logger.warning(f"Could not find '{imdb_title}' on JustWatch for likelist. Skipping.")
        return "not_found"

    logger.info(f"Found JustWatch ID '{justwatch_id}' for '{imdb_title}'.")

    if dry_run:
        logger.info(f"[dry run] Would {action} '{imdb_title}' (ID: {justwatch_id}).")
        return f"would_{action}"

    if action == "like":
        if client.add_to_likelist(justwatch_id):
            logger.success(f"Successfully liked '{imdb_title}' (ID: {justwatch_id}).")
            return "liked"
        logger.error(f"Failed to like '{imdb_title}' (ID: {justwatch_id}).")
    else:
        if client.add_to_dislikelist(justwatch_id):
            logger.success(f"Successfully disliked '{imdb_title}' (ID: {justwatch_id}).")
            return "disliked"
        logger.error(f"Failed to dislike '{imdb_title}' (ID: {justwatch_id}).")

    return "failed"


def main(dry_run: bool) -> None:
    logger.info("Starting IMDb ratings import to JustWatch likelist...")
    if dry_run:
        logger.info("Dry run: titles will be looked up, but nothing will be liked or disliked on your account.")

    if not os.path.exists(CSV_FILE_PATH):
        logger.error(f"CSV file not found at '{CSV_FILE_PATH}'. Please ensure it exists.")
        logger.info("Make sure your IMDb ratings export (ratings.csv) is in the 'exports/' directory.")
        return

    try:
        client = JustWatchClient(country=DEFAULT_COUNTRY, language=DEFAULT_LANGUAGE)
    except ValueError as e:
        logger.critical(f"Failed to initialize JustWatch client: {e}")
        logger.critical("Ensure the JUSTWATCH_AUTH_TOKEN environment variable is set correctly.")
        return

    logger.info(f"Reading ratings items from: {CSV_FILE_PATH}")
    outcomes: Counter[str] = Counter()

    try:
        with open(CSV_FILE_PATH, encoding="ISO-8859-1", newline="") as f:
            csv_reader = csv.DictReader(f)

            # Verify necessary columns exist in the CSV header
            header = csv_reader.fieldnames
            if not header:
                logger.error(f"CSV file at '{CSV_FILE_PATH}' appears to be empty or has no header.")
                return

            required_columns = [IMDB_TITLE_COLUMN, IMDB_TYPE_COLUMN, IMDB_YEAR_COLUMN, IMDB_RATING_COLUMN]
            missing_columns = [col for col in required_columns if col not in header]
            if missing_columns:
                logger.error(f"Missing required columns in '{CSV_FILE_PATH}': {', '.join(missing_columns)}")
                logger.error(f"Available columns: {', '.join(header)}")
                logger.info("Please ensure the CSV file is the IMDb ratings export, which has a 'Your Rating' column.")
                return

            for i, row in enumerate(csv_reader):
                row_num_for_logging = i + 2  # +1 for 1-based index, +1 for header
                logger.debug(f"Reading row {row_num_for_logging}: {row}")
                imdb_title = ""
                try:
                    imdb_title = row.get(IMDB_TITLE_COLUMN, "").strip()
                    imdb_type_str = row.get(IMDB_TYPE_COLUMN, "").strip()
                    imdb_year_str = row.get(IMDB_YEAR_COLUMN, "").strip()
                    imdb_rating_str = row.get(IMDB_RATING_COLUMN, "").strip()

                    if not imdb_title:
                        logger.warning(f"Skipping row {row_num_for_logging} due to empty title.")
                        outcomes["empty_title"] += 1
                        continue

                    outcome = process_likelist_entry(
                        client, imdb_title, imdb_type_str, imdb_year_str, imdb_rating_str, dry_run
                    )
                    outcomes[outcome] += 1

                except Exception:  # Catching general exceptions for safety during row processing
                    logger.exception(
                        f"An unexpected error occurred processing row {row_num_for_logging} ('{imdb_title or 'N/A'}')."
                    )
                    outcomes["error"] += 1
                    continue  # Continue with the next row

                if outcome in NETWORK_OUTCOMES:
                    logger.info(f"Waiting for {REQUEST_DELAY_SECONDS}s before next entry...")
                    sleep(REQUEST_DELAY_SECONDS)

    except FileNotFoundError:
        logger.error(f"CSV file not found at '{CSV_FILE_PATH}'.")  # Should be caught by earlier check but good to have
        return
    except Exception as e:
        logger.critical(f"An unexpected error occurred during CSV processing: {e}")
        return

    logger.info("--- Import Summary ---")
    logger.info(f"Total rows read from CSV: {sum(outcomes.values())}")
    for outcome, count in outcomes.most_common():
        logger.info(f"  {outcome}: {count}")
    logger.success("IMDb ratings import to JustWatch likelist finished.")


if __name__ == "__main__":
    dry_run = parse_dry_run("Like or dislike titles on JustWatch based on your IMDb ratings.")
    configure_logging("import_likelist")

    main(dry_run)

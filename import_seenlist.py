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

CSV_FILE_PATH = os.path.join("exports", "ratings.csv")  # Path to the IMDb ratings CSV

# --- Column Names from ratings.csv ---
# These are the actual header names we expect in the CSV for the relevant data.
IMDB_TITLE_COLUMN = "Title"
IMDB_TYPE_COLUMN = "Title Type"
IMDB_YEAR_COLUMN = "Year"


def process_seenlist_entry(client: JustWatchClient, imdb_title: str, imdb_type: str, imdb_year: str) -> None:
    """Processes a single entry from the ratings CSV for the seenlist."""
    logger.info(f"Processing for seenlist: Title='{imdb_title}', Type='{imdb_type}', Year='{imdb_year}'")

    justwatch_type = map_imdb_type_to_justwatch(imdb_type)
    if not justwatch_type:
        return

    try:
        year_int = int(imdb_year)
    except ValueError:
        logger.warning(f"Invalid year format '{imdb_year}' for title '{imdb_title}'. Attempting search without year.")
        year_int = None

    justwatch_id = client.get_title_id(title_name=imdb_title, title_type=justwatch_type, release_year=year_int)

    if justwatch_id:
        logger.info(f"Found JustWatch ID '{justwatch_id}' for '{imdb_title}'.")
        if client.add_to_seenlist(justwatch_id):
            logger.success(f"Successfully added '{imdb_title}' (ID: {justwatch_id}) to JustWatch seenlist.")
        else:
            logger.error(f"Failed to add '{imdb_title}' (ID: {justwatch_id}) to JustWatch seenlist.")
    else:
        logger.warning(f"Could not find '{imdb_title}' on JustWatch for seenlist. Skipping.")


def main() -> None:
    logger.info("Starting IMDb ratings import to JustWatch seenlist...")

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
    entries_processed = 0

    try:
        with open(CSV_FILE_PATH, encoding="ISO-8859-1", newline="") as f:
            csv_reader = csv.DictReader(f)

            header = csv_reader.fieldnames
            if not header:
                logger.error(f"CSV file at '{CSV_FILE_PATH}' appears to be empty or has no header.")
                return

            required_columns = [IMDB_TITLE_COLUMN, IMDB_TYPE_COLUMN, IMDB_YEAR_COLUMN]
            missing_columns = [col for col in required_columns if col not in header]
            if missing_columns:
                logger.error(f"Missing required columns in '{CSV_FILE_PATH}': {', '.join(missing_columns)}")
                logger.error(f"Available columns: {', '.join(header)}")
                logger.info("Please ensure the CSV file has the correct headers (e.g., 'Title', 'Title Type', 'Year').")
                return

            for i, row in enumerate(csv_reader):
                row_num_for_logging = i + 2  # For logging purposes
                logger.debug(f"Reading row {row_num_for_logging}: {row}")
                try:
                    imdb_title = row.get(IMDB_TITLE_COLUMN, "").strip()
                    imdb_type_str = row.get(IMDB_TYPE_COLUMN, "").strip()
                    imdb_year_str = row.get(IMDB_YEAR_COLUMN, "").strip()

                    if not imdb_title:
                        logger.warning(f"Skipping row {row_num_for_logging} due to empty title.")
                        continue

                    process_seenlist_entry(client, imdb_title, imdb_type_str, imdb_year_str)
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
    logger.info(f"Total entries processed from CSV for seenlist: {entries_processed}")
    logger.success("IMDb ratings import to JustWatch seenlist finished.")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    main()

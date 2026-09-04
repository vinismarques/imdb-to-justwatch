from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# --- Configuration ---
DEFAULT_COUNTRY = "US"
DEFAULT_LANGUAGE = "en-US"
REQUEST_DELAY_SECONDS = 1
LOG_DIR = Path("logs")


def open_imdb_export(path: str | Path) -> io.StringIO:
    """Decodes an IMDb export, guessing the encoding only when UTF-8 is genuinely wrong.

    A wrong guess here fails silently rather than loudly: every latin-1-family codec accepts
    any byte sequence, so decoding UTF-8 as one turns 'Shogun' into mojibake that no longer
    matches anything on JustWatch. Strict UTF-8 first means that mistake raises instead.
    """
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Re-saving an export through Excel is the usual way one stops being UTF-8.
        logger.warning(f"'{path}' is not valid UTF-8. Falling back to cp1252; check titles with accents.")
        text = raw.decode("cp1252", errors="replace")
    return io.StringIO(text, newline="")


def configure_logging(script_name: str) -> Path:
    """Mirrors the run to a timestamped file, so warnings outlive the terminal scrollback."""
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{script_name}-{datetime.now():%Y%m%d-%H%M%S}.log"
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(log_path, level="DEBUG", encoding="utf-8")
    logger.info(f"Writing a full log of this run to {log_path}")
    return log_path


def write_unmatched_report(script_name: str, unmatched: list[dict[str, str]]) -> Path | None:
    """Records the titles a run could not import, which have to be re-entered by hand."""
    if not unmatched:
        return None

    LOG_DIR.mkdir(exist_ok=True)
    report_path = LOG_DIR / f"{script_name}-unmatched-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Title", "Title Type", "Year", "Reason"])
        writer.writeheader()
        writer.writerows(unmatched)
    logger.warning(f"{len(unmatched)} titles need your attention. They are listed in {report_path}")
    return report_path


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

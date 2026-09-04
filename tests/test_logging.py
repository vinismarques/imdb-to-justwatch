"""Run logs are persisted so warnings survive a closed terminal."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from imdb_justwatch_util.shared import configure_logging


def test_run_log_records_warnings_to_a_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    log_path = configure_logging("import_likelist")
    logger.warning("Could not find 'Some Movie' on JustWatch.")

    assert Path(log_path).exists()
    assert "Could not find 'Some Movie'" in Path(log_path).read_text()

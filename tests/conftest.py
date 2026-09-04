from __future__ import annotations

import pytest


class FakeClient:
    """Stands in for JustWatchClient. Records mutations and never touches the network."""

    def __init__(self, missing_titles: set[str] | None = None, mutations_succeed: bool = True, **kwargs) -> None:
        self.missing_titles = missing_titles or set()
        self.mutations_succeed = mutations_succeed
        self.lookups: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def get_title_id(self, title_name: str, title_type: str, release_year: int | None) -> str | None:
        self.lookups.append(title_name)
        if title_name in self.missing_titles:
            return None
        return f"tm_{title_name.replace(' ', '_')}"

    def _record(self, action: str, justwatch_id: str) -> bool:
        self.calls.append((action, justwatch_id))
        return self.mutations_succeed

    def add_to_likelist(self, justwatch_id: str) -> bool:
        return self._record("like", justwatch_id)

    def add_to_dislikelist(self, justwatch_id: str) -> bool:
        return self._record("dislike", justwatch_id)

    def add_to_watchlist(self, justwatch_id: str) -> bool:
        return self._record("watchlist", justwatch_id)

    def add_to_seenlist(self, justwatch_id: str) -> bool:
        return self._record("seenlist", justwatch_id)


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def write_csv(tmp_path):
    """Writes a CSV in the IMDb export encoding and returns its path."""

    def _write(name: str, rows: str) -> str:
        path = tmp_path / name
        path.write_text(rows, encoding="ISO-8859-1")
        return str(path)

    return _write


@pytest.fixture
def run_importer(monkeypatch, write_csv):
    """Runs an importer's main() against a CSV with a fake client. Returns (client, sleep_calls)."""

    def _run(module, csv_text: str, *, dry_run: bool = False, missing_titles: set[str] | None = None):
        fake = FakeClient(missing_titles=missing_titles)
        sleep_calls: list[float] = []
        monkeypatch.setattr(module, "JustWatchClient", lambda **kwargs: fake)
        monkeypatch.setattr(module, "CSV_FILE_PATH", write_csv("input.csv", csv_text))
        monkeypatch.setattr(module, "sleep", sleep_calls.append)
        module.main(dry_run)
        return fake, sleep_calls

    return _run

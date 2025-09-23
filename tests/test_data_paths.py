# @file: test_data_paths.py
from pathlib import Path

from config import Settings


def test_default_paths_under_data(monkeypatch) -> None:
    for key in [
        "DATA_ROOT",
        "DB_PATH",
        "MODEL_REGISTRY_PATH",
        "REPORTS_DIR",
        "LOG_DIR",
        "RUNTIME_LOCK_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert Path(settings.DATA_ROOT) == Path("/data")
    assert Path(settings.DB_PATH).as_posix().startswith("/data")
    assert Path(settings.MODEL_REGISTRY_PATH).as_posix().startswith("/data")
    assert Path(settings.REPORTS_DIR).as_posix().startswith("/data")
    assert Path(settings.LOG_DIR).as_posix().startswith("/data")
    assert Path(settings.RUNTIME_LOCK_PATH).as_posix().startswith("/data")

"""
@file: test_sportmonks_stub.py
@description: Tests for SportMonks client stub behaviour
@dependencies: app/integrations/sportmonks_client.py
@created: 2025-09-15
"""
import importlib
import os


def _import_client():
    module = importlib.import_module("app.integrations.sportmonks_client")
    return importlib.reload(module)


def test_stub_client(monkeypatch):
    monkeypatch.setenv("SPORTMONKS_STUB", "1")
    monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)
    monkeypatch.delenv("SPORTMONKS_API_KEY", raising=False)
    module = _import_client()

    client = module.SportMonksClient()
    leagues = client.leagues()
    assert isinstance(leagues, list)
    assert len(leagues) >= 2
    fixtures = client.fixtures_by_date("2025-01-01")
    assert all("id" in f and "home" in f and "away" in f for f in fixtures)
    monkeypatch.delenv("SPORTMONKS_STUB", raising=False)


def test_stub_auto_enabled(monkeypatch):
    monkeypatch.setenv("SPORTMONKS_API_TOKEN", "dummy")
    module = _import_client()

    client = module.SportMonksClient()

    def _fail(*_args, **_kwargs):  # pragma: no cover - defensive
        raise AssertionError("HTTP should not be invoked in stub mode")

    monkeypatch.setattr(module, "_get", _fail)

    fixtures = client.fixtures_by_date("2025-01-01")
    assert fixtures

"""
@file: test_sportmonks_stub.py
@description: Tests for SportMonks client stub behaviour
@dependencies: app/integrations/sportmonks_client.py
@created: 2025-09-15
"""
import os


def test_stub_client(monkeypatch):
    monkeypatch.setenv("SPORTMONKS_STUB", "1")
    monkeypatch.delenv("SPORTMONKS_API_KEY", raising=False)
    from app.integrations.sportmonks_client import SportMonksClient

    client = SportMonksClient()
    leagues = client.leagues()
    assert isinstance(leagues, list)
    assert len(leagues) >= 2
    fixtures = client.fixtures_by_date("2025-01-01")
    assert all("id" in f and "home" in f and "away" in f for f in fixtures)


def test_stub_auto_enabled(monkeypatch):
    monkeypatch.setenv("SPORTMONKS_API_KEY", "dummy")
    from app.integrations.sportmonks_client import SportMonksConfig

    cfg = SportMonksConfig.from_env()
    assert cfg.stub

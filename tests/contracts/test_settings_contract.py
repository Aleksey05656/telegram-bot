"""
@file: test_settings_contract.py
@description: Contract test for application settings
@dependencies: app.config
@created: 2025-09-10
"""

from app.config import PrometheusSettings, RateLimitSettings, SentrySettings, Settings


def test_settings_contract() -> None:
    s = Settings()
    assert isinstance(s.sentry, SentrySettings)
    assert isinstance(s.prometheus, PrometheusSettings)
    assert isinstance(s.rate_limit, RateLimitSettings)

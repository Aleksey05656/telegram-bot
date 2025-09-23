"""
/**
 * @file: tests/bot/test_subscriptions.py
 * @description: Validate SQLite persistence for preferences and subscriptions.
 * @dependencies: app.bot.storage
 * @created: 2025-09-23
 */
"""

from app.bot import storage


def test_upsert_subscription_stores_data(tmp_path) -> None:
    db_path = tmp_path / "prefs.sqlite3"
    storage.ensure_schema(str(db_path))
    prefs = storage.upsert_user_preferences(123, tz="Europe/Moscow", lang="ru", db_path=str(db_path))
    assert prefs["tz"] == "Europe/Moscow"
    subscription = storage.upsert_subscription(
        123, send_at="09:30", tz="Europe/Moscow", league="epl", db_path=str(db_path)
    )
    assert subscription["send_at"] == "09:30"
    all_subs = storage.list_subscriptions(db_path=str(db_path))
    assert len(all_subs) == 1
    assert all_subs[0]["league"] == "epl"


def test_delete_subscription_removes_row(tmp_path) -> None:
    db_path = tmp_path / "prefs.sqlite3"
    storage.ensure_schema(str(db_path))
    storage.upsert_subscription(321, send_at="08:00", tz="UTC", league=None, db_path=str(db_path))
    storage.delete_subscription(321, db_path=str(db_path))
    assert storage.list_subscriptions(db_path=str(db_path)) == []

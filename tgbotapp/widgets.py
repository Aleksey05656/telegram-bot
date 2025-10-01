"""
@file: tgbotapp/widgets.py
@description: Rendering helpers for Telegram bot responses.
@dependencies: datetime, html
@created: 2025-09-19
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from html import escape
from typing import Any


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.replace(tzinfo=UTC)
            except Exception:  # pragma: no cover - defensive fallback
                return None
    return None


def _format_time(dt: datetime | None) -> str:
    if dt is None:
        return "время уточняется"
    utc_dt = dt.astimezone(UTC)
    return f"{utc_dt:%Y-%m-%d %H:%M} UTC"


def _format_pct(value: float | int) -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return "—"
    if val < 0:
        val = 0.0
    if val <= 1.0000001:
        val *= 100.0
    return f"{val:.1f}%"


def _sorted_scores(items: Iterable[tuple[str, float]]) -> list[tuple[str, float]]:
    return sorted(items, key=lambda item: item[1], reverse=True)


def format_fixture_list(fixtures: list[dict[str, Any]]) -> str:
    """Render fixtures list into Telegram-friendly HTML."""

    if not fixtures:
        return "📭 Матчей не найдено."

    normalized: list[dict[str, Any]] = []
    for fixture in fixtures:
        kickoff = _coerce_datetime(fixture.get("kickoff") or fixture.get("date"))
        normalized.append(
            {
                "id": fixture.get("id"),
                "home": escape(str(fixture.get("home", "—"))),
                "away": escape(str(fixture.get("away", "—"))),
                "league": escape(str(fixture.get("league", ""))),
                "kickoff": kickoff,
            }
        )

    header_date = None
    for item in normalized:
        if item["kickoff"] is not None:
            header_date = item["kickoff"].astimezone(UTC).date()
            break
    header_date_str = header_date.isoformat() if header_date else "выбранную дату"
    lines = [f"📅 <b>Матчи на {header_date_str}</b>"]

    for item in normalized:
        fixture_id = escape(str(item["id"]))
        teams = f"{item['home']} — {item['away']}"
        kickoff = _format_time(item["kickoff"])
        league = f" ({item['league']})" if item["league"] else ""
        lines.append(f"• <code>{fixture_id}</code> — {teams} | {kickoff}{league}")

    return "\n".join(lines)


def format_prediction(payload: dict[str, Any]) -> str:
    """Render prediction payload to HTML with safe formatting."""

    fixture = payload.get("fixture", {}) if isinstance(payload, dict) else {}
    home = escape(str(fixture.get("home", "Неизвестно")))
    away = escape(str(fixture.get("away", "Неизвестно")))
    league = escape(str(fixture.get("league", "")))
    kickoff = _coerce_datetime(fixture.get("kickoff"))
    kickoff_str = _format_time(kickoff) if kickoff else "время уточняется"

    markets = payload.get("markets", {}) if isinstance(payload, dict) else {}
    market_1x2 = markets.get("1x2", {}) if isinstance(markets, dict) else {}
    home_prob = market_1x2.get("home") or market_1x2.get("1") or 0.0
    draw_prob = market_1x2.get("draw") or market_1x2.get("X") or 0.0
    away_prob = market_1x2.get("away") or market_1x2.get("2") or 0.0

    totals_section = []
    totals = payload.get("totals", {}) if isinstance(payload, dict) else {}
    if isinstance(totals, dict) and totals:
        for threshold in sorted(totals.keys()):
            market = totals.get(threshold, {})
            over = market.get("over", 0.0)
            under = market.get("under", 0.0)
            totals_section.append(
                (
                    escape(str(threshold)),
                    _format_pct(over),
                    _format_pct(under),
                )
            )
    else:
        totals_section.append(("2.5", _format_pct(0.0), _format_pct(0.0)))

    btts = payload.get("both_teams_to_score", {})
    if not isinstance(btts, dict):
        btts = {}
    btts_yes = _format_pct(btts.get("yes", 0.0))
    btts_no = _format_pct(btts.get("no", 0.0))

    raw_scores = payload.get("top_scores", [])
    top_scores: list[tuple[str, float]] = []
    if isinstance(raw_scores, dict):
        top_scores = list(raw_scores.items())
    elif isinstance(raw_scores, list):
        for item in raw_scores:
            if isinstance(item, dict):
                score = str(item.get("score"))
                prob = float(item.get("probability", 0.0))
            elif isinstance(item, list | tuple) and len(item) >= 2:
                score = str(item[0])
                prob = float(item[1])
            else:
                continue
            top_scores.append((score, prob))
    top_scores = _sorted_scores(top_scores)[:3]

    top_scores_lines = [
        f"{idx}. {escape(score)} — {_format_pct(prob)}"
        for idx, (score, prob) in enumerate(top_scores, start=1)
    ]
    if not top_scores_lines:
        top_scores_lines = ["Нет данных"]

    header_lines = [
        "🔮 <b>Прогноз на матч</b>",
        f"{home} — {away}",
    ]
    if league:
        header_lines.append(f"Лига: {league}")
    header_lines.append(f"Старт: {kickoff_str}")

    body_lines = [
        "",
        "<b>1X2</b>",
        f"• 1 — {_format_pct(home_prob)}",
        f"• X — {_format_pct(draw_prob)}",
        f"• 2 — {_format_pct(away_prob)}",
        "",
        "<b>Тоталы</b>",
    ]
    for threshold, over, under in totals_section:
        body_lines.append(f"• Тотал {threshold}: Б {over} / М {under}")
    body_lines.extend(
        [
            "",
            "<b>Обе забьют</b>",
            f"• Да — {btts_yes}",
            f"• Нет — {btts_no}",
            "",
            "<b>Топ точных счетов</b>",
            *top_scores_lines,
        ]
    )

    return "\n".join(header_lines + body_lines)

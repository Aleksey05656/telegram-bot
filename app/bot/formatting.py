"""
/**
 * @file: app/bot/formatting.py
 * @description: HTML rendering helpers for Telegram bot responses with safe escaping.
 * @dependencies: html, datetime
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from config import settings

_CONFIDENCE_THRESHOLDS = (
    (0.65, "⬆️"),
    (0.45, "➡️"),
    (0.0, "⬇️"),
)


def _confidence_indicator(value: float) -> str:
    for threshold, marker in _CONFIDENCE_THRESHOLDS:
        if value >= threshold:
            return marker
    return "⬇️"


def _fmt_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_decimal(value: float) -> str:
    return f"{value:.2f}"


def _render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    header_line = "  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    divider = "  ".join("-" * widths[idx] for idx in range(len(headers)))
    if rows:
        body_lines = [
            "  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row)) for row in rows
        ]
        table = "\n".join([header_line, divider, *body_lines])
    else:
        table = "\n".join([header_line, divider, "(нет данных)"])
    return f"<pre>{escape(table)}</pre>"


def _render_freshness(hours: float) -> str:
    if hours < 1:
        minutes = max(1, int(hours * 60))
        return f"🟢 updated {minutes}m ago"
    if hours <= settings.SM_FRESHNESS_WARN_HOURS:
        return f"🟢 updated {int(hours)}h ago"
    if hours <= settings.SM_FRESHNESS_FAIL_HOURS:
        return f"🟡 aging {int(hours)}h"
    return f"⚠️ stale {int(hours)}h"


def _resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def format_start(language: str, tz_name: str, commands: Sequence[str]) -> str:
    header = "👋 <b>Добро пожаловать в Predictions Bot</b>"
    tz_line = f"🕒 <b>Ваш часовой пояс</b>: {escape(tz_name)}"
    lang_line = f"🌐 <b>Язык</b>: {escape(language.upper())}"
    commands_html = "\n".join(f"• {escape(cmd)}" for cmd in commands)
    return "\n".join(
        [
            header,
            "",
            "Этот бот помогает получать вероятностные прогнозы футбольных матчей и объясняет, как формируется уверенность.",
            tz_line,
            lang_line,
            "",
            "Доступные команды:",
            commands_html,
            "",
            "Для подробностей используйте /help",
        ]
    )


def format_help() -> str:
    parts = [
        "ℹ️ <b>Возможности бота</b>",
        "",
        "• /today [league] [market] [limit=N] — свежие матчи с ключевыми рынками",
        "• /match &lt;id|team1 vs team2&gt; — детальная карта матча",
        "• /explain &lt;id&gt; — объяснение λ и модификаторов",
        "• /league &lt;code&gt; [date] — расписание и прогнозы лиги",
        "• /subscribe [HH:MM] [league] — ежедневный дайджест",
        "• /settings — персональные настройки",
        "• /export &lt;match_id&gt; — отчёт CSV/PNG",
        "• /about — техническая информация",
        "",
        "Пример: <code>/today epl limit=5</code> или <code>/match 12345</code>",
    ]
    return "\n".join(parts)


def format_today_matches(
    *,
    title: str,
    timezone: str,
    items: Sequence[dict[str, object]],
    page: int,
    total_pages: int,
    freshness_note: str | None = None,
) -> str:
    tz = _resolve_timezone(timezone)
    when = datetime.now(UTC).astimezone(tz).strftime("%Y-%m-%d %H:%M")
    lines = [f"📅 <b>{escape(title)}</b>", f"🕒 {escape(when)} ({escape(timezone)})"]
    if freshness_note:
        lines.append(freshness_note)
    lines.append("")
    table_rows = []
    for item in items:
        match_line = f"{escape(str(item['home']))} vs {escape(str(item['away']))}"
        probs = item.get("markets", {}) or {}
        home = _fmt_percent(float(probs.get("home", 0.0)))
        draw = _fmt_percent(float(probs.get("draw", 0.0)))
        away = _fmt_percent(float(probs.get("away", 0.0)))
        conf = _confidence_indicator(float(item.get("confidence", 0.5)))
        table_rows.append((match_line, home, draw, away, conf))
    table = _render_table(["Матч", "1", "X", "2", "Ув."], table_rows)
    lines.append(table)
    for item in items:
        totals = (item.get("totals") or {}).get("2.5", {})
        expected = item.get("expected_goals")
        expected_str = f"{float(expected):.2f}" if expected is not None else "—"
        over = _fmt_percent(float(totals.get("over", 0.0))) if totals else "—"
        lines.append(
            f"• {escape(str(item['home']))} vs {escape(str(item['away']))}: E[Goals]={expected_str}, Over2.5={over}"
        )
    lines.append(escape(f"Страница {page}/{total_pages}"))
    return "\n".join(lines)


def format_match_details(data: dict[str, object]) -> str:
    fixture = data.get("fixture", {}) or {}
    title = f"⚽️ <b>{escape(str(fixture.get('home')))} vs {escape(str(fixture.get('away')))}</b>"
    kickoff_raw = fixture.get("kickoff")
    if isinstance(kickoff_raw, datetime):
        kickoff = kickoff_raw.astimezone(_resolve_timezone("UTC")).strftime("%Y-%m-%d %H:%M")
    else:
        kickoff = "N/A"
    league = escape(str(fixture.get("league", "")))
    body = [title, f"🏟️ Лига: {league}", f"🗓️ Начало: {escape(kickoff)}", ""]
    markets = data.get("markets", {}) or {}
    table_rows: list[Sequence[str]] = []
    if "1x2" in markets:
        probs = markets["1x2"] or {}
        table_rows.append(("P(1)", _fmt_percent(float(probs.get("home", 0.0)))))
        table_rows.append(("P(X)", _fmt_percent(float(probs.get("draw", 0.0)))))
        table_rows.append(("P(2)", _fmt_percent(float(probs.get("away", 0.0)))))
    totals = data.get("totals", {}) or {}
    if "2.5" in totals:
        total = totals["2.5"] or {}
        table_rows.append(("Over 2.5", _fmt_percent(float(total.get("over", 0.0)))))
        table_rows.append(("Under 2.5", _fmt_percent(float(total.get("under", 0.0)))))
    btts = data.get("both_teams_to_score", {}) or {}
    if btts:
        table_rows.append(("BTTS", _fmt_percent(float(btts.get("yes", 0.0)))))
    fair = data.get("fair_odds", {}) or {}
    for market, price in fair.items():
        table_rows.append((f"Fair {market}", _fmt_decimal(float(price))))
    body.append(_render_table(["Метрика", "Значение"], table_rows))
    scores = data.get("top_scores", [])
    if scores:
        score_rows = [
            (escape(item.get("score", "?")), _fmt_percent(float(item.get("probability", 0.0))))
            for item in scores
        ]
        body.append("🏅 <b>Топ скорлайны</b>")
        body.append(_render_table(["Счёт", "Вероятность"], score_rows))
    confidence = float(data.get("confidence", 0.5))
    body.append(f"Уровень уверенности: {_confidence_indicator(confidence)} {_fmt_percent(confidence)}")

    freshness = data.get("freshness_hours")
    if isinstance(freshness, (int, float)):
        body.append(_render_freshness(freshness))

    standings = data.get("standings", []) or []
    if standings:
        body.append("🏆 <b>Текущее положение</b>")
        table_rows = [
            (
                escape(str(row.get("team_id"))),
                str(row.get("position", "?")),
                str(row.get("points", "?")),
            )
            for row in standings
        ]
        body.append(_render_table(["Команда", "Поз.", "Очки"], table_rows))

    injuries = data.get("injuries", []) or []
    if injuries:
        body.append("🚑 <b>Травмы</b>")
        injury_rows = [
            (
                escape(str(item.get("player_name"))),
                escape(str(item.get("status", "?"))),
            )
            for item in injuries[:6]
        ]
        body.append(_render_table(["Игрок", "Статус"], injury_rows))
    return "\n".join(body)


def format_explain(payload: dict[str, object]) -> str:
    fixture = payload.get("fixture", {}) or {}
    header = f"🧠 <b>Объяснение прогноза #{escape(str(payload.get('id', '')))}</b>"
    base_home = _fmt_decimal(float(payload.get("lambda_home", 0.0)))
    base_away = _fmt_decimal(float(payload.get("lambda_away", 0.0)))
    mods = payload.get("modifiers", [])
    modifier_rows = [
        (
            escape(mod.get("name", "")),
            _fmt_decimal(float(mod.get("delta", 0.0))),
            _fmt_percent(float(mod.get("impact", 0.0))),
        )
        for mod in mods
    ]
    lines = [
        header,
        f"Матч: {escape(str(fixture.get('home')))} vs {escape(str(fixture.get('away')))}",
        f"λ базовые: {base_home} / {base_away}",
        "",
        "Модификаторы:",
        _render_table(["Фактор", "Δλ", "Δp"], modifier_rows) if modifier_rows else "—",
    ]
    delta_probs = payload.get("delta_probabilities", {}) or {}
    delta_rows = [
        (key, _fmt_percent(float(value))) for key, value in delta_probs.items()
    ]
    if delta_rows:
        lines.append("Изменения вероятностей:")
        lines.append(_render_table(["Рынок", "Δ"], delta_rows))
    confidence = float(payload.get("confidence", 0.5))
    summary = escape(str(payload.get("summary", "")))
    lines.append("")
    lines.append(f"Итог: {summary}")
    lines.append(f"Уверенность: {_confidence_indicator(confidence)} {_fmt_percent(confidence)}")
    freshness = payload.get("freshness_hours")
    if isinstance(freshness, (int, float)):
        lines.append(_render_freshness(freshness))
    standings = payload.get("standings", []) or []
    if standings:
        rows = [
            (
                escape(str(item.get("team_id"))),
                str(item.get("position", "?")),
                str(item.get("points", "?")),
            )
            for item in standings[:6]
        ]
        lines.append("🏆 Турнирная таблица:")
        lines.append(_render_table(["Команда", "Поз.", "Очки"], rows))
    injuries = payload.get("injuries", []) or []
    if injuries:
        rows = [
            (
                escape(str(item.get("player_name"))),
                escape(str(item.get("status", "?"))),
            )
            for item in injuries[:6]
        ]
        lines.append("🚑 Травмы:")
        lines.append(_render_table(["Игрок", "Статус"], rows))
    return "\n".join(lines)


def format_league_listing(
    *,
    league: str,
    target_date: datetime,
    items: Sequence[dict[str, object]],
    page: int,
    total_pages: int,
) -> str:
    heading = f"🏆 <b>{escape(league)}</b> — {escape(target_date.strftime('%Y-%m-%d'))}"
    rows: list[Sequence[str]] = []
    for item in items:
        match_line = f"{escape(str(item['home']))} vs {escape(str(item['away']))}"
        kickoff = item.get("kickoff")
        kickoff_str = (
            kickoff.strftime("%H:%M") if isinstance(kickoff, datetime) else str(kickoff)
        )
        conf = _confidence_indicator(float(item.get("confidence", 0.5)))
        rows.append((match_line, kickoff_str, conf))
    table = _render_table(["Матч", "Время", "Ув."], rows)
    footer = escape(f"Страница {page}/{total_pages}")
    return "\n".join([heading, table, footer])


def format_settings(preferences: dict[str, str | None]) -> str:
    tz = preferences.get("tz") or "UTC"
    lang = preferences.get("lang") or "ru"
    odds = preferences.get("odds_format") or "decimal"
    return "\n".join(
        [
            "⚙️ <b>Ваши настройки</b>",
            f"Часовой пояс: {escape(tz)}",
            f"Язык: {escape(lang.upper())}",
            f"Формат коэффициентов: {escape(odds)}",
        ]
    )


def format_about(metadata: dict[str, object]) -> str:
    lines = ["ℹ️ <b>О системе</b>"]
    for key, value in metadata.items():
        lines.append(f"• {escape(str(key))}: {escape(str(value))}")
    return "\n".join(lines)


def format_digest(matches: Iterable[dict[str, object]], when: datetime) -> str:
    header = f"🌅 <b>Ежедневный дайджест — {escape(when.strftime('%Y-%m-%d'))}</b>"
    rows = []
    for item in matches:
        name = f"{escape(str(item['home']))} vs {escape(str(item['away']))}"
        prob = _fmt_percent(float(item.get("confidence", 0.5)))
        rows.append((name, prob))
    table = _render_table(["Матч", "Уверенность"], rows)
    return "\n".join([header, table])


def format_export_notice(path: str, kind: str) -> str:
    return f"📁 Отчёт {escape(kind.upper())} сохранён в <code>{escape(path)}</code>"


__all__ = [
    "format_start",
    "format_help",
    "format_today_matches",
    "format_match_details",
    "format_explain",
    "format_league_listing",
    "format_settings",
    "format_about",
    "format_digest",
    "format_export_notice",
]

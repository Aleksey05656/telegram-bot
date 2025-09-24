"""
/**
 * @file: app/bot/formatting.py
 * @description: HTML rendering helpers for Telegram bot responses with safe escaping.
 * @dependencies: html, datetime
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from html import escape
from zoneinfo import ZoneInfo

from app.lines.providers.base import OddsSnapshot
from app.value_detector import ValuePick
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


def _format_best_price(best: dict[str, object] | None) -> str | None:
    if not isinstance(best, dict):
        return None
    provider = best.get("provider")
    price = best.get("price_decimal")
    if provider is None or price is None:
        return None
    line = f"Best price: {escape(str(provider))} {_fmt_decimal(float(price))}"
    score = best.get("score")
    if score is not None:
        try:
            line += f" (score={float(score):.2f})"
        except (TypeError, ValueError):
            pass
    pulled = best.get("pulled_at_utc")
    if isinstance(pulled, str):
        line += f" @ {escape(pulled)}"
    return line


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
    if isinstance(freshness, int | float):
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
    if isinstance(freshness, int | float):
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


def format_value_picks(
    *,
    title: str,
    cards: Sequence[dict[str, object]],
) -> str:
    lines = [f"💎 <b>{escape(title)}</b>"]
    if not cards:
        lines.append("Пока нет value-кейсов для заданных фильтров.")
        return "\n".join(lines)
    for card in cards:
        match = card.get("match", {}) or {}
        pick: ValuePick = card.get("pick")  # type: ignore[assignment]
        overround_method = str(card.get("overround_method", "proportional"))
        consensus = card.get("consensus") or {}
        best_price = card.get("best_price") if isinstance(card, dict) else None
        home = escape(str(match.get("home", "?")))
        away = escape(str(match.get("away", "?")))
        league = escape(str(match.get("league", "")))
        kickoff = match.get("kickoff")
        kickoff_str = "N/A"
        if isinstance(kickoff, datetime):
            kickoff_str = kickoff.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
        header = f"• {home} vs {away} ({league}) — {escape(kickoff_str)}"
        market_line = (
            f"{escape(pick.market)} / {escape(pick.selection)}: "
            f"model={_fmt_percent(pick.model_probability)} | "
            f"market={_fmt_percent(pick.market_probability)} | "
            f"edge_w={pick.edge_weighted_pct:.2f}"
        )
        consensus_line = None
        if consensus:
            provider_count = int(consensus.get("provider_count", 0))
            trend = str(consensus.get("trend", "→"))
            price = _fmt_decimal(float(consensus.get("price", pick.market_price)))
            consensus_line = (
                f"Consensus {price} (n={provider_count}) {escape(trend)}"
            )
            closing_price = consensus.get("closing_price")
            if closing_price is not None:
                consensus_line += f" · closing {_fmt_decimal(float(closing_price))}"
        price_line = (
            f"Fair {_fmt_decimal(pick.fair_price)} vs market {_fmt_decimal(pick.market_price)}"
            f" → edge {pick.edge_pct:.1f}% (conf={pick.confidence:.2f})"
        )
        thresholds = (
            f"🧪 Калибровка активна: τ≥{pick.edge_threshold_pct:.1f}%, γ≥{pick.confidence_threshold:.2f}"
            if pick.calibrated
            else f"🧪 Пороги: τ≥{pick.edge_threshold_pct:.1f}%, γ≥{pick.confidence_threshold:.2f}"
        )
        explain = (
            "ℹ️ Объяснение: "
            f"p_model={_fmt_percent(pick.model_probability)}, "
            f"p_market_norm={_fmt_percent(pick.market_probability)}, "
            f"overround={escape(overround_method)}, "
            f"fair={_fmt_decimal(pick.fair_price)}, "
            f"edge={pick.edge_pct:.1f}%, conf={pick.confidence:.2f}, "
            f"edge_w={pick.edge_weighted_pct:.2f}"
        )
        block = [header, market_line]
        if consensus_line:
            block.append(consensus_line)
        best_line = _format_best_price(best_price)
        if best_line:
            block.append(best_line)
        block.extend([price_line, thresholds, explain, f"Источник {escape(pick.provider)}", ""])
        lines.extend(block)
    return "\n".join(lines).strip()


def format_value_comparison(data: dict[str, object]) -> str:
    match = data.get("match", {}) or {}
    home = escape(str(match.get("home", "?")))
    away = escape(str(match.get("away", "?")))
    league = escape(str(match.get("league", "")))
    kickoff = match.get("kickoff")
    kickoff_str = "N/A"
    if isinstance(kickoff, datetime):
        kickoff_str = kickoff.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    overround_method = str(data.get("overround_method", "proportional"))
    lines = [
        f"⚖️ <b>{home} vs {away}</b>",
        f"🏟️ {league} — {escape(kickoff_str)}",
        "",
    ]
    picks: Sequence[ValuePick] = data.get("picks") or []  # type: ignore[assignment]
    if picks:
        lines.append("💎 Value сигналы:")
        for pick in picks:
            lines.append(
                "\n".join(
                    [
                        f"• {escape(pick.market)} / {escape(pick.selection)}",
                        (
                            f"  model={_fmt_percent(pick.model_probability)}"
                            f" market={_fmt_percent(pick.market_probability)}"
                            f" edge={pick.edge_pct:.1f}% edge_w={pick.edge_weighted_pct:.2f}"
                        ),
                        (
                            f"  τ≥{pick.edge_threshold_pct:.1f}% γ≥{pick.confidence_threshold:.2f}"
                            if pick.calibrated
                            else f"  Пороги τ≥{pick.edge_threshold_pct:.1f}% γ≥{pick.confidence_threshold:.2f}"
                        ),
                        (
                            "  "
                            + "ℹ️ "
                            + (
                                f"p_model={_fmt_percent(pick.model_probability)}, "
                                f"p_market_norm={_fmt_percent(pick.market_probability)}, "
                                f"overround={escape(overround_method)}, "
                                f"fair={_fmt_decimal(pick.fair_price)}, "
                                f"edge={pick.edge_pct:.1f}%, conf={pick.confidence:.2f}, "
                                f"edge_w={pick.edge_weighted_pct:.2f}"
                            )
                        ),
                    ]
                )
            )
            consensus_map: dict[tuple[str, str], dict[str, object]] = data.get("consensus", {})  # type: ignore[assignment]
            consensus = consensus_map.get((pick.market.upper(), pick.selection.upper()))
            if consensus:
                provider_count = int(consensus.get("provider_count", 0))
                trend = str(consensus.get("trend", "→"))
                price = _fmt_decimal(float(consensus.get("price", pick.market_price)))
                closing = consensus.get("closing_price")
                closing_str = (
                    f" · closing {_fmt_decimal(float(closing))}" if closing is not None else ""
                )
                lines.append(
                    f"    Consensus {price} (n={provider_count}) {escape(trend)}{closing_str}"
                )
            best_map: dict[tuple[str, str], dict[str, object]] = data.get("best_price", {})  # type: ignore[assignment]
            best_line = _format_best_price(best_map.get((pick.market.upper(), pick.selection.upper())))
            if best_line:
                lines.append(f"    {best_line}")
        lines.append("")
    markets = data.get("markets", {}) or {}
    if not markets:
        lines.append("Для матча нет котировок для сравнения.")
        return "\n".join(lines)
    for market_name, selections in markets.items():
        lines.append(f"<b>{escape(market_name)}</b>")
        table_rows: list[Sequence[str]] = []
        for selection, payload in selections.items():
            model_p = float(payload.get("model_p", 0.0))
            market_p = float(payload.get("market_p", 0.0))
            price = float(payload.get("price", 0.0))
            fair = float("inf") if model_p <= 0 else 1.0 / model_p
            edge = (fair / price - 1.0) * 100 if price > 0 and fair != float("inf") else 0.0
            fair_str = "∞" if fair == float("inf") else _fmt_decimal(fair)
            table_rows.append(
                (
                    escape(selection),
                    _fmt_percent(model_p),
                    _fmt_percent(market_p),
                    fair_str,
                    _fmt_decimal(price),
                    f"{edge:.1f}%",
                )
            )
        lines.append(
            _render_table(
                ["Исход", "Model", "Market", "Fair", "Price", "Edge"],
                table_rows,
            )
        )
        lines.append("")
    return "\n".join(lines).strip()


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


def format_providers_breakdown(
    *,
    match_key: str,
    market: str,
    selection: str,
    quotes: Sequence[OddsSnapshot],
    consensus: dict[str, object] | None,
) -> str:
    lines = [
        f"📊 <b>{escape(market)} / {escape(selection)}</b>",
        f"Матч: {escape(match_key)}",
    ]
    if consensus:
        provider_count = int(consensus.get("provider_count", 0))
        trend = str(consensus.get("trend", "→"))
        price = _fmt_decimal(float(consensus.get("price", 0.0)))
        closing = consensus.get("closing_price")
        closing_part = (
            f" · closing {_fmt_decimal(float(closing))}" if closing is not None else ""
        )
        lines.append(f"Consensus {price} (n={provider_count}) {escape(trend)}{closing_part}")
    if not quotes:
        lines.append("Нет активных котировок по провайдерам.")
        return "\n".join(lines)
    lines.append("Провайдеры:")
    for quote in quotes:
        pulled = quote.pulled_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"• {escape(quote.provider)} — {_fmt_decimal(quote.price_decimal)} ({pulled} UTC)"
        )
    return "\n".join(lines)


def format_portfolio(summary: dict[str, object]) -> str:
    total = int(summary.get("total", 0))
    avg_clv = float(summary.get("avg_clv", 0.0))
    avg_edge = float(summary.get("avg_edge", 0.0))
    avg_roi = float(summary.get("avg_roi", 0.0))
    positive_share = float(summary.get("positive_share", 0.0)) * 100
    page = int(summary.get("page", 1))
    total_pages = int(summary.get("total_pages", 1))
    rolling_days = int(getattr(settings, "PORTFOLIO_ROLLING_DAYS", 60))
    lines = [
        "📈 <b>Портфель</b>",
        f"Всего сигналов: {total}",
        f"Средний edge: {avg_edge:.2f}%",
        f"Средний CLV: {avg_clv:.2f}%",
        f"Положительный CLV: {positive_share:.1f}%",
        f"ROI {rolling_days}д: {avg_roi:.2f}%",
        f"Страница {page}/{total_pages}",
    ]
    picks = summary.get("picks") or []
    if not picks:
        lines.append("")
        lines.append("История пока пуста — используйте /value, чтобы начать.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Последние записи:")
    for row in picks:
        market = escape(str(row.get("market", "")))
        selection = escape(str(row.get("selection", "")))
        match_key = escape(str(row.get("match_key", "N/A")))
        provider_price = _fmt_decimal(float(row.get("provider_price_decimal", row.get("price_taken", 0.0))))
        consensus_price = row.get("consensus_price_decimal")
        consensus_part = ""
        if consensus_price is not None:
            consensus_part = f" vs cons {_fmt_decimal(float(consensus_price))}"
        closing_price = row.get("closing_price")
        if closing_price is not None:
            consensus_part += f" / close {_fmt_decimal(float(closing_price))}"
        roi = row.get("roi")
        roi_part = f" ROI {float(roi):+.1f}%" if roi is not None else ""
        outcome = str(row.get("outcome") or "—").upper()
        clv = row.get("clv_pct")
        clv_part = f" CLV {float(clv):+.2f}%" if clv is not None else " CLV —"
        created_raw = row.get("created_at")
        created_str = str(created_raw)
        if isinstance(created_raw, str):
            try:
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                created_str = created_dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                created_str = created_raw
        lines.append(
            " • ".join(
                [
                    f"{match_key} · {market}/{selection}",
                    f"{provider_price}{consensus_part}",
                    f"{outcome}{roi_part}{clv_part}",
                    f"{escape(created_str)}",
                ]
            )
        )
    return "\n".join(lines)


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
    "format_value_picks",
    "format_value_comparison",
    "format_providers_breakdown",
    "format_portfolio",
]

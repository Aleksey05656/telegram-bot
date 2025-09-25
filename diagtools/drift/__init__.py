"""
/**
 * @file: diagtools/drift/__init__.py
 * @description: Drift diagnostics CLI with PSI/KS metrics, stratification and CI gating.
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence, TYPE_CHECKING

from types import ModuleType
from scipy.stats import ks_2samp

if TYPE_CHECKING:  # pragma: no cover - aid static typing only
    import numpy as np  # type: ignore
    import pandas as pd  # type: ignore
else:
    class _LazyModule:
        def __init__(self, module_name: str) -> None:
            self._module_name = module_name
            self._module: ModuleType | None = None

        def _load(self) -> ModuleType:
            if self._module is None:
                self._module = importlib.import_module(self._module_name)
            return self._module

        def __getattr__(self, item: str):  # pragma: no cover - trivial proxy
            return getattr(self._load(), item)

        def __dir__(self) -> list[str]:  # pragma: no cover - trivial proxy
            return dir(self._load())

    np = _LazyModule("numpy")
    pd = _LazyModule("pandas")

try:  # pragma: no cover - matplotlib optional in some environments
    from matplotlib import pyplot as plt

    HAS_MPL = True
except ModuleNotFoundError:  # pragma: no cover - plotting is optional
    plt = None  # type: ignore[assignment]
    HAS_MPL = False

from diagtools.golden_regression import _simulate_dataset

DEFAULT_FEATURES = [
    "home_xg",
    "away_xg",
    "home_xga",
    "away_xga",
    "form_home",
    "form_away",
    "home_advantage",
    "fatigue_delta",
]

SEVERITY_ORDER = {"OK": 0, "WARN": 1, "FAIL": 2}


@dataclass(slots=True)
class DriftThresholds:
    psi_warn: float
    psi_fail: float
    ks_p_warn: float
    ks_p_fail: float


@dataclass(slots=True)
class DriftConfig:
    reports_dir: Path
    ref_days: int
    ref_rolling_days: int
    thresholds: DriftThresholds
    dataset_path: Path | None = None
    current_path: Path | None = None
    ref_path: Path | None = None
    features: Sequence[str] = field(default_factory=lambda: list(DEFAULT_FEATURES))
    date_column: str = "match_date"
    league_column: str = "league"
    season_column: str = "season"
    top_feature_limit: int = 5


@dataclass(slots=True)
class ReferenceWindow:
    name: str
    frame: pd.DataFrame
    start: datetime | None
    end: datetime | None
    source: str


@dataclass(slots=True)
class MetricRow:
    reference: str
    scope: str
    identifier: str
    feature: str
    psi: float
    ks_stat: float
    p_value: float
    n_ref: int
    n_cur: int
    status: str
    note: str


@dataclass(slots=True)
class ScopeSummaryRow:
    reference: str
    scope: str
    identifier: str
    max_psi: float
    min_p_value: float
    status: str


@dataclass(slots=True)
class DriftResult:
    metrics: list[MetricRow]
    summary: list[ScopeSummaryRow]
    status_by_reference: dict[str, dict[str, str]]
    worst_status: str
    summary_path: Path
    json_path: Path
    csv_paths: dict[str, Path]
    reference_meta_path: Path
    plot_paths: list[Path]


def _load_frame(path: Path) -> pd.DataFrame:
    if not path.exists():  # pragma: no cover - safety net for CLI usage
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.suffix.lower() in {".csv", ".txt"}:
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_parquet(path)
    return df


def _ensure_datetime(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        return
    df[column] = pd.to_datetime(df[column], utc=True, errors="coerce").dt.tz_localize(None)


def _synthetic_dataset() -> pd.DataFrame:
    df = _simulate_dataset(n_rows=360, seed=20241012).rename(columns={"date": "match_date"})
    rng = np.random.default_rng(20241012)
    leagues = ["EPL", "LaLiga", "SerieA", "Bundesliga"]
    df["league"] = rng.choice(leagues, size=len(df))
    df["season"] = (df["match_date"].dt.year.astype(str) + "/" + (df["match_date"].dt.year + 1).astype(str))
    df.sort_values("match_date", inplace=True)
    return df


def _derive_current_slice(dataset: pd.DataFrame, config: DriftConfig, *, add_synthetic_drift: bool) -> pd.DataFrame:
    if config.date_column not in dataset.columns:
        return dataset.copy()
    dataset = dataset.sort_values(config.date_column)
    end = dataset[config.date_column].max()
    if pd.isna(end):
        return dataset.copy()
    start = end - timedelta(days=max(config.ref_rolling_days - 1, 0))
    current = dataset[dataset[config.date_column] >= start].copy()
    if current.empty:
        return dataset.tail(max(config.ref_rolling_days, 1)).copy()
    if add_synthetic_drift:
        if "home_xg" in current.columns:
            current["home_xg"] *= 1.02
        if "away_xg" in current.columns:
            current["away_xg"] *= 0.99
        if "form_home" in current.columns:
            current["form_home"] += 0.03
        if "home_advantage" in current.columns:
            current["home_advantage"] += 0.005
    return current


def _window_slice(dataset: pd.DataFrame, column: str, end: datetime, days: int) -> tuple[pd.DataFrame, datetime | None, datetime | None]:
    if column not in dataset.columns or days <= 0:
        return dataset.copy(), None, None
    window_end = end - timedelta(days=1)
    window_start = window_end - timedelta(days=days - 1)
    mask = (dataset[column] >= window_start) & (dataset[column] <= window_end)
    frame = dataset.loc[mask].copy()
    if frame.empty:
        frame = dataset[dataset[column] < end].tail(days).copy()
    start = frame[column].min() if column in frame.columns else None
    stop = frame[column].max() if column in frame.columns else None
    return frame, start, stop


def _prepare_datasets(
    config: DriftConfig,
    dataset: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, ReferenceWindow]]:
    synthetic = False
    base = dataset.copy() if dataset is not None else None
    if base is None and config.dataset_path:
        base = _load_frame(config.dataset_path)
    if base is None and config.current_path and config.dataset_path is None:
        base = _load_frame(config.current_path)
    if base is None and config.ref_path:
        base = _load_frame(config.ref_path)
    if base is None:
        base = _synthetic_dataset()
        synthetic = True
    base = base.copy()
    _ensure_datetime(base, config.date_column)
    if config.current_path and config.dataset_path is None and dataset is None:
        current = _load_frame(config.current_path).copy()
        _ensure_datetime(current, config.date_column)
    else:
        current = _derive_current_slice(base, config, add_synthetic_drift=synthetic)
    references: dict[str, ReferenceWindow] = {}
    current_start = current[config.date_column].min() if config.date_column in current.columns else None
    if config.ref_path:
        ref_df = _load_frame(config.ref_path)
        ref_df = ref_df.copy()
        _ensure_datetime(ref_df, config.date_column)
        start = ref_df[config.date_column].min() if config.date_column in ref_df.columns else None
        end = ref_df[config.date_column].max() if config.date_column in ref_df.columns else None
        references["anchor"] = ReferenceWindow("anchor", ref_df, start, end, source="file")
    if current_start is not None and not pd.isna(current_start):
        if config.dataset_path or dataset is not None or not references:
            anchor_frame, anchor_start, anchor_end = _window_slice(
                base,
                config.date_column,
                current_start,
                max(config.ref_days, 0),
            )
            if not anchor_frame.empty:
                references.setdefault(
                    "anchor",
                    ReferenceWindow("anchor", anchor_frame, anchor_start, anchor_end, source="window"),
                )
            rolling_frame, rolling_start, rolling_end = _window_slice(
                base,
                config.date_column,
                current_start,
                max(config.ref_rolling_days, 0),
            )
            if not rolling_frame.empty:
                references["rolling"] = ReferenceWindow(
                    "rolling",
                    rolling_frame,
                    rolling_start,
                    rolling_end,
                    source="window",
                )
    if not references:
        references["anchor"] = ReferenceWindow(
            "anchor",
            base.copy(),
            base[config.date_column].min() if config.date_column in base.columns else None,
            base[config.date_column].max() if config.date_column in base.columns else None,
            source="fallback",
        )
    return current, references


def _compute_psi(reference: np.ndarray, current: np.ndarray, bins: int = 15) -> float:
    combined = np.concatenate([reference, current])
    if combined.size == 0:
        return float("nan")
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(combined, quantiles))
    if edges.size <= 1:
        return 0.0
    ref_hist, edges = np.histogram(reference, bins=edges)
    cur_hist, _ = np.histogram(current, bins=edges)
    ref_prop = ref_hist / max(ref_hist.sum(), 1)
    cur_prop = cur_hist / max(cur_hist.sum(), 1)
    psi = 0.0
    for ref_p, cur_p in zip(ref_prop, cur_prop, strict=False):
        if ref_p <= 0 and cur_p <= 0:
            continue
        ref_p = max(ref_p, 1e-6)
        cur_p = max(cur_p, 1e-6)
        psi += (cur_p - ref_p) * math.log(cur_p / ref_p)
    return float(psi)


def _evaluate_feature(
    feature: str,
    ref_series: pd.Series,
    cur_series: pd.Series,
    thresholds: DriftThresholds,
) -> tuple[float, float, float, str, str]:
    ref_values = ref_series.dropna().to_numpy()
    cur_values = cur_series.dropna().to_numpy()
    if ref_values.size == 0 or cur_values.size == 0:
        return float("nan"), float("nan"), float("nan"), "WARN", "insufficient data"
    psi = _compute_psi(ref_values, cur_values)
    ks_stat, p_value = ks_2samp(ref_values, cur_values, alternative="two-sided", mode="auto")
    status = "OK"
    note = "stable"
    if math.isnan(psi) or math.isnan(p_value):
        status = "WARN"
        note = "metrics unavailable"
    elif psi >= thresholds.psi_fail or p_value <= thresholds.ks_p_fail:
        status = "FAIL"
        note = f"psi={psi:.3f}, p={p_value:.4f}"
    elif psi >= thresholds.psi_warn or p_value <= thresholds.ks_p_warn:
        status = "WARN"
        note = f"psi={psi:.3f}, p={p_value:.4f}"
    return float(psi), float(ks_stat), float(p_value), status, note


def _iter_scopes(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    config: DriftConfig,
) -> Iterable[tuple[str, str, pd.DataFrame, pd.DataFrame]]:
    yield "global", "all", reference, current
    league_col = config.league_column
    if league_col in reference.columns or league_col in current.columns:
        values = sorted(
            set(reference.get(league_col, pd.Series(dtype=str)).dropna().unique()).union(
                set(current.get(league_col, pd.Series(dtype=str)).dropna().unique())
            )
        )
        for value in values:
            ref_slice = reference[reference.get(league_col) == value]
            cur_slice = current[current.get(league_col) == value]
            yield "league", str(value), ref_slice, cur_slice
    season_col = config.season_column
    if season_col in reference.columns or season_col in current.columns:
        values = sorted(
            set(reference.get(season_col, pd.Series(dtype=str)).dropna().unique()).union(
                set(current.get(season_col, pd.Series(dtype=str)).dropna().unique())
            )
        )
        for value in values:
            ref_slice = reference[reference.get(season_col) == value]
            cur_slice = current[current.get(season_col) == value]
            yield "season", str(value), ref_slice, cur_slice


def _collect_metrics(
    current: pd.DataFrame,
    references: dict[str, ReferenceWindow],
    config: DriftConfig,
) -> list[MetricRow]:
    metrics: list[MetricRow] = []
    for ref_name, window in references.items():
        ref_frame = window.frame
        for scope, identifier, ref_slice, cur_slice in _iter_scopes(ref_frame, current, config):
            if ref_slice.empty or cur_slice.empty:
                psi, ks_stat, p_value, status, note = float("nan"), float("nan"), float("nan"), "WARN", "insufficient data"
                metrics.append(
                    MetricRow(
                        ref_name,
                        scope,
                        identifier,
                        "__all__",
                        psi,
                        ks_stat,
                        p_value,
                        len(ref_slice),
                        len(cur_slice),
                        status,
                        note,
                    )
                )
                continue
            for feature in config.features:
                if feature not in ref_slice.columns or feature not in cur_slice.columns:
                    continue
                psi, ks_stat, p_value, status, note = _evaluate_feature(
                    feature,
                    ref_slice[feature],
                    cur_slice[feature],
                    config.thresholds,
                )
                metrics.append(
                    MetricRow(
                        ref_name,
                        scope,
                        identifier,
                        feature,
                        psi,
                        ks_stat,
                        p_value,
                        len(ref_slice),
                        len(cur_slice),
                        status,
                        note,
                    )
                )
    return metrics


def _aggregate_summary(metrics: Sequence[MetricRow], thresholds: DriftThresholds) -> list[ScopeSummaryRow]:
    accumulator: dict[tuple[str, str, str], dict[str, list[float]]] = {}
    for metric in metrics:
        key = (metric.reference, metric.scope, metric.identifier)
        entry = accumulator.setdefault(key, {"psi": [], "p": []})
        if not math.isnan(metric.psi):
            entry["psi"].append(metric.psi)
        if not math.isnan(metric.p_value):
            entry["p"].append(metric.p_value)
    summary: list[ScopeSummaryRow] = []
    for (reference, scope, identifier), values in accumulator.items():
        psi_values = values["psi"]
        p_values = values["p"]
        max_psi = max(psi_values) if psi_values else float("nan")
        min_p = min(p_values) if p_values else float("nan")
        status = _status_from_values(max_psi, min_p, thresholds)
        summary.append(ScopeSummaryRow(reference, scope, identifier, max_psi, min_p, status))
    return summary


def _status_from_values(psi: float, p_value: float, thresholds: DriftThresholds) -> str:
    if math.isnan(psi) or math.isnan(p_value):
        return "WARN"
    if psi >= thresholds.psi_fail or p_value <= thresholds.ks_p_fail:
        return "FAIL"
    if psi >= thresholds.psi_warn or p_value <= thresholds.ks_p_warn:
        return "WARN"
    return "OK"


def _status_matrix(summary: Sequence[ScopeSummaryRow]) -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = {}
    for row in summary:
        scope_map = matrix.setdefault(row.reference, {})
        prev = scope_map.get(row.scope, "OK")
        if SEVERITY_ORDER[row.status] > SEVERITY_ORDER.get(prev, 0):
            scope_map[row.scope] = row.status
    for reference, scope_map in matrix.items():
        overall = "OK"
        for status in scope_map.values():
            if SEVERITY_ORDER[status] > SEVERITY_ORDER[overall]:
                overall = status
        scope_map["overall"] = overall
    return matrix


def _write_reference_artifacts(
    references: dict[str, ReferenceWindow],
    reports_dir: Path,
    config: DriftConfig,
) -> Path:
    reference_dir = reports_dir / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict[str, object]] = {}
    for name, window in references.items():
        path = reference_dir / f"{name}.parquet"
        storage_format = _write_parquet_with_fallback(window.frame, path)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        (reference_dir / f"{name}.sha256").write_text(checksum + "\n", encoding="utf-8")
        start = window.start.isoformat() if window.start else None
        end = window.end.isoformat() if window.end else None
        meta[name] = {
            "source": window.source,
            "start": start,
            "end": end,
            "rows": int(window.frame.shape[0]),
            "format": storage_format,
        }
    meta_path = reference_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta_path


def _write_csv(metrics: Sequence[MetricRow], reports_dir: Path) -> dict[str, Path]:
    df = pd.DataFrame(
        [
            {
                "reference": m.reference,
                "scope": m.scope,
                "identifier": m.identifier,
                "feature": m.feature,
                "psi": m.psi,
                "ks_stat": m.ks_stat,
                "p_value": m.p_value,
                "n_ref": m.n_ref,
                "n_cur": m.n_cur,
                "status": m.status,
                "note": m.note,
            }
            for m in metrics
        ]
    )
    csv_paths: dict[str, Path] = {}
    for scope in {"global", "league", "season"}:
        scope_df = df[df["scope"] == scope].copy()
        if scope_df.empty:
            continue
        path = reports_dir / f"{scope}.csv"
        scope_df.to_csv(path, index=False)
        csv_paths[scope] = path
    return csv_paths


def _render_markdown(
    reports_dir: Path,
    summary: Sequence[ScopeSummaryRow],
    matrix: dict[str, dict[str, str]],
    references: dict[str, ReferenceWindow],
) -> Path:
    lines: list[str] = ["# Drift Summary", ""]
    lines.append("## Reference windows")
    for name, window in references.items():
        start = window.start.isoformat() if window.start else "n/a"
        end = window.end.isoformat() if window.end else "n/a"
        lines.append(f"- **{name}** ({window.source}): {start} → {end}, rows={window.frame.shape[0]}")
    lines.append("")
    lines.append("## Scope status")
    lines.append("| Reference | Scope | Status |")
    lines.append("| --- | --- | --- |")
    for reference, scopes in sorted(matrix.items()):
        for scope, status in sorted(scopes.items()):
            lines.append(f"| {reference} | {scope} | {status} |")
    lines.append("")
    lines.append("## Detailed maxima")
    lines.append("| Reference | Scope | Identifier | max PSI | min p-value | Status |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in sorted(summary, key=lambda x: (x.reference, x.scope, x.identifier)):
        lines.append(
            f"| {row.reference} | {row.scope} | {row.identifier} | {row.max_psi:.4f} | {row.min_p_value:.4f} | {row.status} |"
        )
    path = reports_dir / "drift_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_json(
    reports_dir: Path,
    metrics: Sequence[MetricRow],
    summary: Sequence[ScopeSummaryRow],
    matrix: dict[str, dict[str, str]],
    references: dict[str, ReferenceWindow],
) -> Path:
    payload = {
        "references": {
            name: {
                "start": window.start.isoformat() if window.start else None,
                "end": window.end.isoformat() if window.end else None,
                "rows": int(window.frame.shape[0]),
                "source": window.source,
            }
            for name, window in references.items()
        },
        "summary": [dataclasses.asdict(row) for row in summary],
        "metrics": [dataclasses.asdict(row) for row in metrics],
        "status": matrix,
    }
    path = reports_dir / "drift_summary.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _select_top_features(metrics: Sequence[MetricRow], limit: int) -> list[tuple[str, str]]:
    ranking: dict[tuple[str, str], float] = {}
    for metric in metrics:
        if math.isnan(metric.psi):
            continue
        key = (metric.reference, metric.feature)
        ranking[key] = max(ranking.get(key, 0.0), metric.psi)
    ordered = sorted(ranking.items(), key=lambda item: item[1], reverse=True)
    return [item[0] for item in ordered[:limit]]


def _plot_distributions(
    current: pd.DataFrame,
    references: dict[str, ReferenceWindow],
    features: Sequence[tuple[str, str]],
    reports_dir: Path,
    config: DriftConfig,
) -> list[Path]:
    if not HAS_MPL:
        return []
    plot_dir = reports_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for ref_name, feature in features:
        if feature not in current.columns:
            continue
        window = references.get(ref_name)
        if window is None or feature not in window.frame.columns:
            continue
        ref_series = window.frame[feature].dropna()
        cur_series = current[feature].dropna()
        if ref_series.empty or cur_series.empty:
            continue
        plt.figure(figsize=(6, 4))
        plt.hist(ref_series, bins=20, alpha=0.6, label=f"{ref_name} reference")
        plt.hist(cur_series, bins=20, alpha=0.6, label="current")
        plt.title(f"{feature} distribution")
        plt.legend()
        plt.tight_layout()
        path = plot_dir / f"{ref_name}_{feature}.png"
        plt.savefig(path)
        plt.close()
        paths.append(path)
    return paths


def _write_parquet_with_fallback(frame: pd.DataFrame, path: Path) -> str:
    try:
        frame.to_parquet(path, index=False)
        return "parquet"
    except Exception:  # pragma: no cover - fallback for minimal environments
        frame.to_pickle(path)
        return "pickle"


def run(
    config: DriftConfig,
    *,
    current_df: pd.DataFrame | None = None,
    reference_frames: dict[str, pd.DataFrame] | None = None,
    dataset: pd.DataFrame | None = None,
) -> DriftResult:
    reports_dir = config.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    if current_df is None or reference_frames is None:
        current_df, reference_windows = _prepare_datasets(config, dataset=dataset)
    else:
        reference_windows = {}
        for name, frame in reference_frames.items():
            frame = frame.copy()
            _ensure_datetime(frame, config.date_column)
            start = frame[config.date_column].min() if config.date_column in frame.columns else None
            end = frame[config.date_column].max() if config.date_column in frame.columns else None
            reference_windows[name] = ReferenceWindow(name, frame, start, end, source="in-memory")
        current_df = current_df.copy()
        _ensure_datetime(current_df, config.date_column)
    metrics = _collect_metrics(current_df, reference_windows, config)
    summary = _aggregate_summary(metrics, config.thresholds)
    matrix = _status_matrix(summary)
    worst_status = "OK"
    for scope_map in matrix.values():
        status = scope_map.get("overall", "OK")
        if SEVERITY_ORDER[status] > SEVERITY_ORDER[worst_status]:
            worst_status = status
    reference_meta_path = _write_reference_artifacts(reference_windows, reports_dir, config)
    csv_paths = _write_csv(metrics, reports_dir)
    summary_path = _render_markdown(reports_dir, summary, matrix, reference_windows)
    json_path = _write_json(reports_dir, metrics, summary, matrix, reference_windows)
    top_features = _select_top_features(metrics, config.top_feature_limit)
    plot_paths = _plot_distributions(current_df, reference_windows, top_features, reports_dir, config)
    return DriftResult(
        metrics=metrics,
        summary=summary,
        status_by_reference=matrix,
        worst_status=worst_status,
        summary_path=summary_path,
        json_path=json_path,
        csv_paths=csv_paths,
        reference_meta_path=reference_meta_path,
        plot_paths=plot_paths,
    )


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:  # pragma: no cover - defensive for invalid env values
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:  # pragma: no cover
        return default


def _parse_args(argv: Sequence[str] | None = None) -> DriftConfig:
    parser = argparse.ArgumentParser(description="Diagnostics drift detector v2.1")
    parser.add_argument("--dataset-path", type=Path, default=None, help="Historical dataset with match_date column")
    parser.add_argument("--current-path", type=Path, default=None, help="Explicit current dataset (CSV/Parquet)")
    parser.add_argument("--ref-path", type=Path, default=None, help="Precomputed reference dataset (overrides anchor window)")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports/diagnostics/drift"),
        help="Directory to persist drift artefacts",
    )
    parser.add_argument(
        "--ref-days",
        type=int,
        default=_env_int("DRIFT_REF_DAYS", 90),
        help="Anchor reference window in days",
    )
    parser.add_argument(
        "--ref-rolling-days",
        type=int,
        default=_env_int("DRIFT_ROLLING_DAYS", 30),
        help="Rolling reference window in days",
    )
    parser.add_argument(
        "--psi-warn",
        type=float,
        default=_env_float("DRIFT_PSI_WARN", 0.10),
        help="PSI warning threshold",
    )
    parser.add_argument(
        "--psi-fail",
        type=float,
        default=_env_float("DRIFT_PSI_FAIL", 0.25),
        help="PSI failure threshold",
    )
    parser.add_argument(
        "--ks-p-warn",
        type=float,
        default=_env_float("DRIFT_KS_P_WARN", 0.05),
        help="KS p-value warning threshold",
    )
    parser.add_argument(
        "--ks-p-fail",
        type=float,
        default=_env_float("DRIFT_KS_P_FAIL", 0.01),
        help="KS p-value failure threshold",
    )
    parser.add_argument(
        "--features",
        nargs="*",
        default=None,
        help="Specific feature columns to evaluate (default: core match features)",
    )
    parser.add_argument("--date-column", default="match_date", help="Name of date column for windowing")
    parser.add_argument("--league-column", default="league", help="League column for stratification")
    parser.add_argument("--season-column", default="season", help="Season column for stratification")
    parser.add_argument(
        "--top-features",
        type=int,
        default=5,
        help="Number of top PSI features to plot",
    )
    args = parser.parse_args(argv)
    thresholds = DriftThresholds(
        psi_warn=args.psi_warn,
        psi_fail=args.psi_fail,
        ks_p_warn=args.ks_p_warn,
        ks_p_fail=args.ks_p_fail,
    )
    features = args.features or list(DEFAULT_FEATURES)
    return DriftConfig(
        reports_dir=args.reports_dir,
        ref_days=args.ref_days,
        ref_rolling_days=args.ref_rolling_days,
        thresholds=thresholds,
        dataset_path=args.dataset_path,
        current_path=args.current_path,
        ref_path=args.ref_path,
        features=features,
        date_column=args.date_column,
        league_column=args.league_column,
        season_column=args.season_column,
        top_feature_limit=args.top_features,
    )


def main(argv: Sequence[str] | None = None) -> None:
    config = _parse_args(argv)
    result = run(config)
    payload = {
        "status": result.worst_status,
        "summary": str(result.summary_path),
        "json": str(result.json_path),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result.worst_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()

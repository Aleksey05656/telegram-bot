"""
/**
 * @file: app/data_quality/__init__.py
 * @description: Public entrypoint for data quality contracts, checks and reporting utilities.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .contracts import MatchContract, default_match_contract
from .report import DataQualityReport, persist_report
from .runner import DataQualityIssue, DataQualityRunner

__all__ = [
    "DataQualityIssue",
    "DataQualityReport",
    "DataQualityRunner",
    "MatchContract",
    "default_match_contract",
    "persist_report",
]


def run_quality_suite(
    dataframe: pd.DataFrame,
    *,
    contract: MatchContract | None = None,
    output_dir: Path,
) -> DataQualityReport:
    """Execute the full data quality suite on *dataframe* and persist artifacts.

    Parameters
    ----------
    dataframe:
        Dataset with match-level rows.
    contract:
        Optional override of the default :class:`MatchContract`.
    output_dir:
        Base directory where CSV artifacts and the summary markdown will be stored.
    """

    contract = contract or default_match_contract()
    runner = DataQualityRunner(contract)
    issues: Iterable[DataQualityIssue] = runner.run_all(dataframe)
    return persist_report(issues, output_dir)

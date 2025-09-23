"""
/**
 * @file: app/data_quality/runner.py
 * @description: Execution harness orchestrating data quality checks.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Protocol

import pandas as pd

from .contracts import MatchContract


class CheckProtocol(Protocol):
    def __call__(self, df: pd.DataFrame, contract: MatchContract) -> "DataQualityIssue":
        ...


@dataclass
class DataQualityIssue:
    name: str
    status: str
    summary: str
    violations: pd.DataFrame | None

    def has_violations(self) -> bool:
        return self.violations is not None and not self.violations.empty


class DataQualityRunner:
    """Apply the registered data quality checks to a dataframe."""

    def __init__(self, contract: MatchContract, checks: Iterable[CheckProtocol] | None = None) -> None:
        from . import checks as check_module

        self.contract = contract
        if checks is None:
            # The default order is curated to surface schema issues first.
            self.checks: tuple[CheckProtocol, ...] = (
                check_module.schema_check,
                check_module.match_key_check,
                check_module.missing_values_check,
                check_module.negative_expected_goals_check,
                check_module.outlier_percentile_check,
                check_module.league_consistency_check,
                check_module.season_overlap_check,
            )
        else:
            self.checks = tuple(checks)

    def run_all(self, df: pd.DataFrame) -> Iterator[DataQualityIssue]:
        for check in self.checks:
            yield check(df, self.contract)

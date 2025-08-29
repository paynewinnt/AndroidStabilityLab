from __future__ import annotations

from .formatting_helpers import PerformanceFormattingHelpersMixin
from .home_help import PerformanceHomeHelpMixin
from .issue_cards import PerformanceIssueCardsMixin
from .metrics_cards import PerformanceMetricsCardsMixin
from .record_cards import PerformanceRecordCardsMixin


class PerformanceIssuesPageMixin(
    PerformanceFormattingHelpersMixin,
    PerformanceRecordCardsMixin,
    PerformanceHomeHelpMixin,
    PerformanceMetricsCardsMixin,
    PerformanceIssueCardsMixin,
):
    pass


__all__ = ["PerformanceIssuesPageMixin"]

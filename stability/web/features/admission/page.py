from __future__ import annotations

from .detail_page import AdmissionDetailPageMixin
from .golden_page import GoldenAdmissionPageMixin
from .quality_page import QualityPageMixin
from .record_page import AdmissionRecordPageMixin

__all__ = [
    "AdmissionDetailPageMixin",
    "GoldenAdmissionPageMixin",
    "QualityPageMixin",
    "AdmissionRecordPageMixin",
]

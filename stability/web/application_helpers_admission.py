from __future__ import annotations

from .application_common import *


class ApplicationAdmissionHelpersMixin:
    @staticmethod
    def _comparison_report_links(history: list[Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in history:
            detail_path = str(getattr(entry, "comparison_detail_path", "") or "").strip()
            comparison_id = str(getattr(entry, "comparison_id", "") or "").strip()
            if not detail_path or not comparison_id or comparison_id in seen:
                continue
            detail = Path(detail_path)
            items.append(
                {
                    "comparison_id": comparison_id,
                    "action": str(getattr(entry, "action", "") or ""),
                    "changed_at": WebPortalApplication._isoformat_or_none(getattr(entry, "changed_at", None)),
                    "report_id": str(getattr(entry, "report_id", "") or ""),
                    "detail_path": detail_path,
                    "markdown_path": str(detail.with_name("summary.md")),
                    "html_path": str(detail.with_name("report.html")),
                }
            )
            seen.add(comparison_id)
        return items

    @staticmethod
    def _baseline_status_summary(
        *,
        report: Mapping[str, Any],
        comparison_reports: list[dict[str, Any]],
        latest_audit: Mapping[str, Any],
        golden_suite: Mapping[str, Any],
    ) -> dict[str, str]:
        def has_any_path(payload: Mapping[str, Any]) -> bool:
            return any(str(payload.get(key, "") or "").strip() for key in ("detail_path", "markdown_path", "html_path"))

        golden_case_total = int(golden_suite.get("case_count_total", 0) or 0)
        golden_failed_total = int(golden_suite.get("failed_case_count_total", 0) or 0)
        if golden_case_total <= 0:
            golden_status = "missing"
        elif golden_failed_total > 0:
            golden_status = "fail"
        else:
            golden_status = "pass"

        return {
            "review": "ready" if has_any_path(report) else "missing",
            "comparison": "ready" if comparison_reports else "missing",
            "audit": "ready" if has_any_path(latest_audit) else "missing",
            "golden": golden_status,
        }

    @staticmethod
    def _baseline_status_actions(summary: Mapping[str, Any]) -> dict[str, str]:
        review_status = str(summary.get("review", "missing") or "missing")
        comparison_status = str(summary.get("comparison", "missing") or "missing")
        audit_status = str(summary.get("audit", "missing") or "missing")
        golden_status = str(summary.get("golden", "missing") or "missing")
        return {
            "review": "查看当前报告摘要" if review_status == "ready" else "先确认 review report 是否已生成",
            "comparison": "查看 comparison reports" if comparison_status == "ready" else "当前没有 comparison report，可先看 baseline history",
            "audit": "查看 latest audit 摘要" if audit_status == "ready" else "先检查 baseline audit 是否已生成",
            "golden": (
                "黄金样本通过，可继续看当前报告"
                if golden_status == "pass"
                else "先展开 Golden Suite，定位失败 case"
                if golden_status == "fail"
                else "当前没有 golden suite 结果，先回看 review"
            ),
        }


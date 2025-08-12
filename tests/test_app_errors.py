from __future__ import annotations

import unittest

from stability.domain import AppError, AppErrorCode, normalize_app_error


class AppErrorTest(unittest.TestCase):
    def test_app_error_serializes_stable_contract(self) -> None:
        error = AppError.validation(
            "参数错误",
            code=AppErrorCode.INVALID_TASK_PARAMS,
            hint="检查模板参数。",
            details={"field": "loop_count"},
        ).with_context(request_id="request-1", audit_event_id="audit-1")

        payload = error.to_dict()

        self.assertEqual(payload["code"], "invalid_task_params")
        self.assertEqual(payload["message"], "参数错误")
        self.assertEqual(payload["hint"], "检查模板参数。")
        self.assertEqual(payload["details"], {"field": "loop_count"})
        self.assertEqual(payload["request_id"], "request-1")
        self.assertEqual(payload["audit_event_id"], "audit-1")

    def test_normalize_existing_exception_types(self) -> None:
        self.assertEqual(normalize_app_error(ValueError("bad")).code, "validation_error")
        self.assertEqual(normalize_app_error(PermissionError("no")).code, "permission_denied")
        self.assertEqual(normalize_app_error(LookupError("missing")).code, "not_found")


if __name__ == "__main__":
    unittest.main()

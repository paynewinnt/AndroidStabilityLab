from __future__ import annotations

from datetime import datetime, timezone
import unittest

from stability.time_utils import (
    coerce_datetime,
    format_beijing_datetime,
    format_beijing_datetime_or_original,
    now_beijing_string,
    serialize_datetime,
    utcnow,
)


class TimeUtilsTest(unittest.TestCase):
    def test_format_beijing_datetime_converts_naive_utc_datetime(self) -> None:
        value = datetime(2025, 7, 25, 3, 45, 53, 900919)

        self.assertEqual(format_beijing_datetime(value), "2025-07-25 11:45:53.900919")

    def test_format_beijing_datetime_converts_iso_string(self) -> None:
        self.assertEqual(
            format_beijing_datetime("2025-07-24T19:00:00"),
            "2025-07-25 03:00:00.000000",
        )
        self.assertEqual(
            format_beijing_datetime("2025-07-24T19:00:00Z"),
            "2025-07-25 03:00:00.000000",
        )

    def test_format_beijing_datetime_preserves_aware_datetime(self) -> None:
        value = datetime(2025, 7, 25, 3, 45, 53, 900919, tzinfo=timezone.utc)

        self.assertEqual(format_beijing_datetime(value), "2025-07-25 11:45:53.900919")

    def test_format_beijing_datetime_or_original_keeps_non_datetime_strings(self) -> None:
        self.assertEqual(format_beijing_datetime_or_original("2025-07-25"), "2025-07-25")
        self.assertIsNone(coerce_datetime("2025-07-25"))

    def test_utcnow_returns_naive_utc_datetime_for_existing_domain_models(self) -> None:
        value = utcnow()

        self.assertIsInstance(value, datetime)
        self.assertIsNone(value.tzinfo)

    def test_unified_serializers_use_beijing_display_format(self) -> None:
        value = datetime(2025, 7, 25, 3, 45, 53, 900919)

        self.assertEqual(serialize_datetime(value), "2025-07-25 11:45:53.900919")
        self.assertRegex(now_beijing_string(), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}$")


if __name__ == "__main__":
    unittest.main()

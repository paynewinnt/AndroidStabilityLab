from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from stability.app import IssueFingerprintGovernanceService
from stability.domain import IssueFingerprint


class IssueFingerprintGovernanceServiceTest(unittest.TestCase):
    def test_alias_rule_persists_and_resolves_to_canonical_fingerprint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IssueFingerprintGovernanceService(root_dir=temp_dir)

            rule = service.upsert_alias(
                source_fingerprint="ifp_old",
                canonical_fingerprint="ifp_new",
                reason="same crash family",
                created_by="qa",
            )
            resolved = IssueFingerprintGovernanceService(root_dir=temp_dir).resolve_fingerprint(
                IssueFingerprint(value="ifp_old", rule_version="v1", components={"issue_type": "crash"})
            )

        self.assertEqual(rule.action, "alias")
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.value, "ifp_new")
        self.assertEqual(resolved.rule_version, "v1+governance")
        self.assertEqual(resolved.components["governance"]["original_fingerprint"], "ifp_old")

    def test_suppress_rule_hides_fingerprint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IssueFingerprintGovernanceService(root_dir=temp_dir)
            service.suppress_fingerprint(fingerprint="ifp_noise", reason="known noisy lab device")

            resolved = service.resolve_fingerprint(IssueFingerprint(value="ifp_noise"))

        self.assertIsNone(resolved)

    def test_remove_rule_restores_default_resolution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IssueFingerprintGovernanceService(root_dir=temp_dir)
            service.suppress_fingerprint(fingerprint="ifp_noise")

            removed = service.remove_rule("ifp_noise")
            resolved = service.resolve_fingerprint(IssueFingerprint(value="ifp_noise"))

        self.assertTrue(removed)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.value, "ifp_noise")


if __name__ == "__main__":
    unittest.main()

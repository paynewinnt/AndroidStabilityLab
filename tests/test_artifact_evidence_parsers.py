from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.artifact.evidence_parsers import parse_artifact_evidence
from stability.domain import ArtifactType


class ArtifactEvidenceParsersTest(unittest.TestCase):
    def test_parse_surfaceflinger_extracts_display_signals(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "surfaceflinger.txt"
            path.write_text(
                "\n".join(
                    [
                        "SurfaceFlinger state",
                        "visible layers: 0",
                        "SurfaceView com.example.app black screen no refresh",
                    ]
                ),
                encoding="utf-8",
            )

            result = parse_artifact_evidence(ArtifactType.DUMPSYS_SURFACEFLINGER, path)

            self.assertEqual(result["parser"], "surfaceflinger")
            self.assertIn("black_screen", result["issue_hints"])
            self.assertIn("freeze", result["issue_hints"])
            self.assertIn("surfaceflinger", result["matched_sources"])
            self.assertIn("frame_refresh", result["matched_sources"])
            self.assertTrue(result["matched_fragments"])

    def test_parse_dropbox_extracts_watchdog_and_system_server_signals(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "dropbox.txt"
            path.write_text(
                "\n".join(
                    [
                        "2025-07-28 10:00:00 system_server_watchdog (text, 120 bytes)",
                        "*** WATCHDOG KILLING SYSTEM PROCESS: Blocked in handler on ActivityManager",
                        "2025-07-28 10:01:00 system_server_crash (text, 80 bytes)",
                        "FATAL EXCEPTION: main",
                        "Process: system_server, PID: 1234",
                    ]
                ),
                encoding="utf-8",
            )

            result = parse_artifact_evidence(ArtifactType.DROPBOX, path)

            self.assertEqual(result["parser"], "dropbox")
            self.assertIn("watchdog", result["issue_hints"])
            self.assertIn("system_server_crash", result["issue_hints"])
            self.assertEqual(result["metrics"]["tag_counts"]["system_server_watchdog"], 1)
            self.assertEqual(result["metrics"]["tag_counts"]["system_server_crash"], 1)

    def test_parse_perfetto_scans_text_tokens_without_requiring_trace_decoder(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "trace.perfetto-trace"
            path.write_bytes(
                b"\x00\x01system_server SurfaceFlinger frame_timeline android.network_packets watchdog\x00"
            )

            result = parse_artifact_evidence(ArtifactType.PERFETTO_TRACE, path)

            self.assertEqual(result["parser"], "perfetto")
            self.assertIn("system_server_context", result["issue_hints"])
            self.assertIn("surfaceflinger_context", result["issue_hints"])
            self.assertIn("network_context", result["issue_hints"])
            self.assertEqual(result["metrics"]["size_bytes"], path.stat().st_size)


if __name__ == "__main__":
    unittest.main()

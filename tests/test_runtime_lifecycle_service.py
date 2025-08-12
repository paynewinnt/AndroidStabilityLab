from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from stability.app import RuntimeLifecycleService


class RuntimeLifecycleServiceTest(unittest.TestCase):
    def test_doctor_summarizes_runtime_categories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            target = root / "tasks" / "task-a"
            target.mkdir(parents=True)
            (target / "run.json").write_text("{}", encoding="utf-8")

            result = RuntimeLifecycleService(root).doctor()

        self.assertTrue(result.ok)
        self.assertEqual(result.total_file_count, 1)
        tasks = [item for item in result.summaries if item.category == "tasks" and item.exists]
        self.assertEqual(tasks[0].file_count, 1)

    def test_export_writes_zip_with_manifest_and_selected_category_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            target = root / "integration_outbox"
            target.mkdir(parents=True)
            (target / "events.json").write_text("[]", encoding="utf-8")
            output = Path(temp_dir) / "runtime.zip"

            result = RuntimeLifecycleService(root).export(output, categories=["integration"])

            self.assertTrue(output.exists())
            self.assertEqual(result.included_files, 1)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("manifest.json", names)
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                self.assertEqual(manifest["categories"], ["integration"])
                self.assertTrue(any(name.endswith("runtime/integration_outbox/events.json") for name in names))

    def test_cleanup_defaults_to_dry_run_and_apply_deletes_old_candidates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            old_task = root / "tasks" / "task-old"
            old_task.mkdir(parents=True)
            (old_task / "run.json").write_text("{}", encoding="utf-8")
            old_timestamp = 1_700_000_000
            os.utime(old_task, (old_timestamp, old_timestamp))
            os.utime(old_task / "run.json", (old_timestamp, old_timestamp))

            service = RuntimeLifecycleService(root)
            dry_run = service.cleanup(categories=["tasks"], max_age_days=1)
            self.assertTrue(old_task.exists())
            applied = service.cleanup(categories=["tasks"], max_age_days=1, apply=True)

            self.assertFalse(dry_run.deleted_paths)
            self.assertEqual(len(dry_run.candidates), 1)
            self.assertEqual(len(applied.deleted_paths), 1)
            self.assertFalse(old_task.exists())


if __name__ == "__main__":
    unittest.main()

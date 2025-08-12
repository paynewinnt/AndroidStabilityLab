from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from typing import Any
from unittest.mock import patch

from stability.cli import task_create


def run_main_with_bundle(argv: list[str], bundle: Any) -> dict[str, Any]:
    with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = task_create.main(argv)
    if exit_code != 0:
        raise AssertionError(f"Expected exit code 0, got {exit_code}")
    return json.loads(stdout.getvalue())

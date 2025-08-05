from __future__ import annotations

import argparse

from stability.cli.parser_analysis import register_analysis_commands
from stability.cli.parser_integration import register_integration_commands
from stability.cli.parser_rules import register_rule_commands
from stability.cli.parser_runtime import register_runtime_commands
from stability.cli.parser_tasks import register_task_commands


def build_parser(handler_module: object | None = None) -> argparse.ArgumentParser:
    """Create the V1 CLI parser for task creation, run creation, and run execution."""
    if handler_module is None:
        from stability.cli import task_create as handler_module

    parser = argparse.ArgumentParser(
        prog="python -m stability.cli",
        description="Minimal V1 CLI for creating V1 task definitions and execution runs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_task_commands(subparsers, handler_module)
    register_analysis_commands(subparsers, handler_module)
    register_rule_commands(subparsers, handler_module)
    register_integration_commands(subparsers, handler_module)
    register_runtime_commands(subparsers, handler_module)
    return parser

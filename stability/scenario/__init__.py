"""Scenario runners for concrete V1 execution templates."""

from .base import ScenarioExecutionResult, ScenarioRunner
from .cold_start_loop import ColdStartLoopScenarioRunner
from .custom_automation import CustomAutomationScenarioRunner
from .device_cycle import (
    ForegroundBackgroundLoopScenarioRunner,
    InstallUninstallLoopScenarioRunner,
    RebootLoopScenarioRunner,
    StandbyWakeLoopScenarioRunner,
)
from .monkey import MonkeyScenarioRunner
from .registry import (
    COMMON_PARAM_SECTION,
    METRIC_REGISTRY,
    SCENARIO_REGISTRY,
    ScenarioDefinition,
    ScenarioMetric,
    ScenarioParamField,
    ScenarioParamSection,
    get_param_sections_for_web,
    get_scenario_definition,
    get_supported_template_values,
    list_scenario_definitions,
    metric_template_scopes,
    resolve_scenario_definition,
    validate_scenario_task_contract,
)

__all__ = [
    "ColdStartLoopScenarioRunner",
    "CustomAutomationScenarioRunner",
    "ForegroundBackgroundLoopScenarioRunner",
    "InstallUninstallLoopScenarioRunner",
    "MonkeyScenarioRunner",
    "RebootLoopScenarioRunner",
    "COMMON_PARAM_SECTION",
    "METRIC_REGISTRY",
    "SCENARIO_REGISTRY",
    "ScenarioDefinition",
    "ScenarioExecutionResult",
    "ScenarioMetric",
    "ScenarioParamField",
    "ScenarioParamSection",
    "ScenarioRunner",
    "StandbyWakeLoopScenarioRunner",
    "get_param_sections_for_web",
    "get_scenario_definition",
    "get_supported_template_values",
    "list_scenario_definitions",
    "metric_template_scopes",
    "resolve_scenario_definition",
    "validate_scenario_task_contract",
]

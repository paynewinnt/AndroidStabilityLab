from __future__ import annotations

import unittest

from stability.domain import AppError, TaskTemplateType
from stability.scenario.registry import (
    METRIC_REGISTRY,
    get_param_sections_for_web,
    get_scenario_definition,
    get_supported_template_values,
    get_template_form_schema,
    list_scenario_definitions,
    metric_template_scopes,
    validate_scenario_task_contract,
)


class ScenarioRegistryTest(unittest.TestCase):
    def test_registry_covers_every_task_template_enum(self) -> None:
        self.assertEqual(
            get_supported_template_values(),
            tuple(item.value for item in TaskTemplateType),
        )

    def test_definitions_expose_user_facing_contract(self) -> None:
        definition = get_scenario_definition(TaskTemplateType.REBOOT_LOOP)

        self.assertEqual(definition.chinese_name, "重启循环")
        self.assertEqual(definition.risk_level, "high")
        self.assertTrue(definition.changes_device_state)
        self.assertIn("power", definition.supported_metrics)
        self.assertIn("reboot_loop", definition.option_label)

    def test_web_param_sections_include_common_and_template_specific_fields(self) -> None:
        sections = get_param_sections_for_web()
        scopes_to_keys = {
            scope: {field.key for section in sections for field in section.fields for scope in section.template_scopes}
            for section in sections
            for scope in section.template_scopes
        }

        self.assertIn("loop_count", scopes_to_keys["all"])
        self.assertIn("event_count", scopes_to_keys["monkey"])
        self.assertIn("apk_path", scopes_to_keys["install_uninstall_loop"])

    def test_metric_scopes_are_derived_from_template_support(self) -> None:
        self.assertIn("gpu", METRIC_REGISTRY)
        self.assertIn("monkey", metric_template_scopes("gpu"))
        self.assertIn("custom", metric_template_scopes("gpu"))
        self.assertNotIn("cold_start_loop", metric_template_scopes("gpu"))

    def test_template_form_schema_exports_web_cli_contract(self) -> None:
        schema = get_template_form_schema(TaskTemplateType.REBOOT_LOOP)

        self.assertEqual(schema["contract"], "scenario_template_schema.v1")
        self.assertEqual(schema["template_type"], "reboot_loop")
        self.assertEqual(schema["risk"]["risk_level"], "high")
        self.assertTrue(schema["risk"]["changes_device_state"])
        self.assertIn("cpu", schema["metrics"]["default"])
        self.assertIn("power", [item["key"] for item in schema["metrics"]["supported"]])
        field_keys = {
            field["key"]
            for section in schema["parameter_sections"]
            for field in section["fields"]
        }
        self.assertIn("loop_count", field_keys)
        self.assertIn("reboot_timeout_seconds", field_keys)

    def test_definition_order_is_stable(self) -> None:
        self.assertEqual(
            [item.value for item in list_scenario_definitions()],
            [item.value for item in TaskTemplateType],
        )

    def test_validate_task_contract_rejects_invalid_template_params(self) -> None:
        with self.assertRaises(AppError) as ctx:
            validate_scenario_task_contract(
                template_type=TaskTemplateType.INSTALL_UNINSTALL_LOOP,
                task_params={"loop_count": "abc"},
                enabled_metrics=["cpu"],
            )

        self.assertEqual(ctx.exception.code, "invalid_task_params")
        self.assertEqual(ctx.exception.details["template_type"], "install_uninstall_loop")
        error_codes = {item["code"] for item in ctx.exception.details["errors"]}
        self.assertIn("required", error_codes)
        self.assertIn("invalid_number", error_codes)

    def test_validate_task_contract_rejects_unsupported_metrics(self) -> None:
        with self.assertRaises(AppError) as ctx:
            validate_scenario_task_contract(
                template_type=TaskTemplateType.COLD_START_LOOP,
                task_params={},
                enabled_metrics=["gpu"],
            )

        self.assertEqual(ctx.exception.code, "unsupported_metric")
        self.assertEqual(ctx.exception.details["unsupported_metrics"], ["gpu"])


if __name__ == "__main__":
    unittest.main()

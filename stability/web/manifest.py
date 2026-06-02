from __future__ import annotations

from typing import Any, Iterable, Mapping


PAGE_ENTRIES: tuple[dict[str, str], ...] = (
    {"label": "首页", "path": "/", "description": "首页摘要和关键状态入口"},
    {"label": "平台说明", "path": "/platform", "description": "平台模式、运行边界和共享入口说明"},
    {"label": "诊断中心", "path": "/doctor", "description": "本地环境、ADB、runtime、Web 和 outbox 诊断"},
    {"label": "设备池", "path": "/device-pools", "description": "设备发现、设备池、连接和设备画像"},
    {"label": "快捷 ADB", "path": "/quick-adb", "description": "常用 ADB 动作和包名查询"},
    {"label": "任务大厅", "path": "/tasks", "description": "任务定义、创建和最近执行入口"},
    {"label": "Run 列表", "path": "/runs", "description": "Run 历史、执行状态和详情入口"},
    {"label": "长稳模板", "path": "/long-run-templates", "description": "长稳任务模板和无人值守配置入口"},
    {"label": "性能采样", "path": "/performance", "description": "监控快照、趋势和 trace 链接"},
    {"label": "产物中心", "path": "/artifacts", "description": "Run 产物、报告和证据索引"},
    {"label": "问题中心", "path": "/issues", "description": "Top Issue 聚合、样本和协作状态"},
    {"label": "巡检状态", "path": "/runner", "description": "无人值守 runner、心跳、日报和周报"},
    {"label": "集成 Outbox", "path": "/integration", "description": "出站事件、worker、receipt 和 dead-letter 运维"},
    {"label": "Golden Suite", "path": "/goldens", "description": "规则回放 golden suite 样本和 diff"},
    {"label": "准入中心", "path": "/admission", "description": "规则准入、基线、审计和对比"},
    {"label": "规则中心", "path": "/rules", "description": "规则配置只读视图和候选预览入口"},
    {"label": "接口中心", "path": "/json-api", "description": "当前 JSON API 的可读入口和原始数据导航"},
)


READ_ENDPOINTS: tuple[dict[str, str], ...] = (
    {"label": "平台说明", "path": "/api/platform", "description": "平台模式、共享入口、就绪状态和 API 清单"},
    {"label": "平台健康", "path": "/api/platform-health", "description": "平台自监控快照，覆盖 runner、ADB、任务、证据抓取和 outbox 健康指标", "kind": "health"},
    {"label": "诊断中心", "path": "/api/doctor", "description": "检查 Python、ADB、设备、runtime、Web、监控 backend 和 outbox webhook", "kind": "health"},
    {"label": "API Manifest", "path": "/api/manifest", "description": "正式 API manifest，汇总页面、读写端点、响应边界和回调合同"},
    {"label": "OpenAPI", "path": "/api/openapi.json", "description": "OpenAPI 风格描述，供共享入口和外部系统对接参考"},
    {"label": "首页摘要", "path": "/api/home", "description": "首页总览聚合数据"},
    {"label": "用户目录", "path": "/api/users", "description": "本地 actor、外部身份和团队/权限只读目录"},
    {"label": "责任同步", "path": "/api/responsibility", "description": "问题、准入、提测和缺陷责任线索检索视图"},
    {"label": "设备池", "path": "/api/device-pools", "description": "设备池、连接状态、画像和调度摘要"},
    {"label": "快捷 ADB", "path": "/api/quick-adb", "description": "快捷 ADB 命令目录、执行历史和设备摘要"},
    {"label": "快捷 ADB 包名查询", "path": "/api/quick-adb/packages", "description": "按设备和 scope 查询可选包名"},
    {"label": "任务大厅", "path": "/api/tasks", "description": "任务和 Run 组合列表"},
    {"label": "任务详情", "path": "/api/tasks/task/<task_id>", "description": "单个任务定义、最近 Run 和关联入口", "kind": "detail"},
    {"label": "Run 列表", "path": "/api/runs", "description": "Run 列表与执行状态"},
    {"label": "Run 详情", "path": "/api/runs/<run_id>", "description": "单个 Run 的实例、报告、日志和产物详情", "kind": "detail"},
    {"label": "长稳模板", "path": "/api/long-run-templates", "description": "长稳模板、参数说明和 runner 入口"},
    {"label": "性能采样", "path": "/api/performance", "description": "最近监控快照、趋势、trace 和性能 risk item 字段"},
    {"label": "产物中心", "path": "/api/artifacts", "description": "Run 产物索引"},
    {"label": "Run 产物", "path": "/api/artifacts/run/<run_id>", "description": "单个 Run 的报告、日志、trace 和 issue 证据产物", "kind": "detail"},
    {"label": "提测请求", "path": "/api/release-submissions", "description": "提测请求列表和准入状态"},
    {"label": "提测详情", "path": "/api/release-submissions/<submission_id>", "description": "单个提测请求的准入、负责人和外部链接详情", "kind": "detail"},
    {"label": "集成 Outbox", "path": "/api/integration", "description": "集成 outbox 总览、worker、webhook 和投递状态"},
    {"label": "问题中心", "path": "/api/issues", "description": "问题中心聚合、样本、协作和缺陷线索"},
    {"label": "巡检状态", "path": "/api/runner", "description": "巡检 runner 状态、心跳、日报、周报和最近 patrol 历史"},
    {"label": "无人值守任务", "path": "/api/runner/unattended/<task_id>", "description": "单个无人值守任务的配置、轮次和调度状态", "kind": "detail"},
    {"label": "Golden Suite", "path": "/api/goldens", "description": "Golden Suite 总览、样本计数和过滤结果"},
    {"label": "Golden Case", "path": "/api/goldens/case/<case_id>", "description": "单条 golden case 的 dataset、规则和 expected 详情", "kind": "detail"},
    {"label": "准入中心", "path": "/api/admission", "description": "准入中心总览、质量门禁和基线摘要"},
    {"label": "准入基线", "path": "/api/admission/baseline/<baseline_key>", "description": "单条准入基线的报告、latest audit、comparison 和时间线", "kind": "detail"},
    {"label": "Admission Cases", "path": "/api/admission/cases", "description": "稳定 AdmissionCase 合同与列表入口"},
    {"label": "Admission Reports", "path": "/api/admission/reports/<baseline_key>", "description": "正式准入报告 JSON，需要替换 baseline_key", "kind": "detail"},
    {"label": "规则中心", "path": "/api/rules", "description": "规则配置中心，只读展示当前版本、校验状态、可编辑字段、风险提示和预览入口"},
    {"label": "集成 Outbox 事件", "path": "/api/integration/outbox", "description": "集成 outbox 事件、投递、receipt 和 dead-letter 状态"},
    {"label": "Ready", "path": "/ready", "description": "团队入口 ready 检查和关键服务就绪状态", "kind": "health"},
    {"label": "Health", "path": "/health", "description": "服务健康检查", "kind": "health"},
)


WRITE_ACTIONS: tuple[dict[str, str], ...] = (
    {"label": "创建任务", "path": "/api/tasks/actions/create-task", "description": "创建任务定义"},
    {"label": "创建 Run", "path": "/api/tasks/actions/create-run", "description": "基于任务创建 Run"},
    {"label": "执行 Run", "path": "/api/tasks/actions/execute-run", "description": "触发 Run 执行"},
    {"label": "停止 Run", "path": "/api/tasks/actions/stop-run", "description": "停止正在运行的 Run"},
    {"label": "归档任务", "path": "/api/tasks/actions/archive-task", "description": "归档任务定义"},
    {"label": "配置无人值守", "path": "/api/runner/actions/configure-unattended", "description": "配置无人值守任务"},
    {"label": "执行无人值守单轮", "path": "/api/runner/actions/run-unattended-round", "description": "立即执行一轮无人值守任务"},
    {"label": "巡检", "path": "/api/runner/actions/patrol-unattended", "description": "触发到期无人值守任务巡检"},
    {"label": "刷新设备", "path": "/api/device-pools/actions/refresh", "description": "刷新设备池状态"},
    {"label": "连接设备", "path": "/api/device-pools/actions/connect", "description": "连接 TCP 设备"},
    {"label": "无线配对并连接设备", "path": "/api/device-pools/actions/pair-connect", "description": "执行无线配对并连接设备"},
    {"label": "设备标记", "path": "/api/device-pools/actions/update-profile", "description": "更新设备画像、标签或维护状态"},
    {"label": "执行快捷 ADB", "path": "/api/quick-adb/actions/execute", "description": "执行快捷 ADB 命令"},
    {"label": "创建提测请求", "path": "/api/release-submissions/actions/create", "description": "创建提测请求"},
    {"label": "问题协作", "path": "/api/issues/actions/assign", "description": "处理问题认领、评论或状态流转"},
    {"label": "准入协作", "path": "/api/admission/actions/transition", "description": "处理准入认领、评论或状态流转"},
    {"label": "集成 worker", "path": "/api/integration/actions/run-worker", "description": "执行 outbox worker"},
    {"label": "Outbox 死信回放", "path": "/api/integration/actions/replay-dead-letters", "description": "预览或执行 dead-letter 回放"},
    {"label": "CI 准入同步", "path": "/api/integration/actions/sync-ci-admission-decisions", "description": "同步 CI 准入决策"},
)


def _copy_entries(entries: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    return [dict(item) for item in entries]


def platform_surface() -> dict[str, list[dict[str, str]]]:
    return {
        "pages": _copy_entries(PAGE_ENTRIES),
        "api_endpoints": _copy_entries(READ_ENDPOINTS),
        "write_actions": _copy_entries(WRITE_ACTIONS),
    }


def api_endpoint_description(path: str) -> str:
    for item in (*READ_ENDPOINTS, *WRITE_ACTIONS):
        if str(item.get("path", "") or "") == str(path or ""):
            return str(item.get("description", "") or "")
    return "当前接口没有额外说明。"


def api_endpoint_kind(path: str) -> str:
    for item in READ_ENDPOINTS:
        if str(item.get("path", "") or "") == str(path or ""):
            return str(item.get("kind", "") or "") or ("detail" if "<" in str(path or "") else "read")
    if "<" in str(path or ""):
        return "detail"
    return "read"


def manifest_summary(surface: Mapping[str, Any] | None = None) -> dict[str, int]:
    data = dict(surface or platform_surface())
    read_endpoints = list(data.get("api_endpoints", []) or [])
    return {
        "page_count": len(list(data.get("pages", []) or [])),
        "read_endpoint_count": len(read_endpoints),
        "write_action_count": len(list(data.get("write_actions", []) or [])),
        "detail_endpoint_count": sum(1 for item in read_endpoints if api_endpoint_kind(str(dict(item).get("path", "") or "")) == "detail"),
        "health_endpoint_count": sum(1 for item in read_endpoints if api_endpoint_kind(str(dict(item).get("path", "") or "")) == "health"),
    }


__all__ = [
    "PAGE_ENTRIES",
    "READ_ENDPOINTS",
    "WRITE_ACTIONS",
    "api_endpoint_description",
    "api_endpoint_kind",
    "manifest_summary",
    "platform_surface",
]

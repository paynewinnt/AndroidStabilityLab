from __future__ import annotations

from html import escape
from typing import Any, Mapping
from urllib.parse import quote


def sidebar_nav(page_title: str) -> str:
    links = [
        ("首页", "/", "首页"),
        ("平台说明", "/platform", "平台说明"),
        ("诊断中心", "/doctor", "诊断中心"),
        ("设备池", "/device-pools", "设备池"),
        ("快捷 ADB", "/quick-adb", "快捷 ADB"),
        ("任务大厅", "/tasks", "任务大厅"),
        ("长稳模板", "/long-run-templates", "长稳运行模板"),
        ("巡检状态", "/runner", "巡检状态"),
        ("性能采样", "/performance", "性能采样"),
        ("问题中心", "/issues", "问题中心"),
        ("集成 Outbox", "/integration", "集成 Outbox"),
        ("Golden Suite", "/goldens", "Golden Suite"),
        ("准入中心", "/admission", "准入中心"),
        ("规则中心", "/rules", "规则中心"),
        ("接口中心", "/json-api", "JSON API"),
    ]
    return "".join(
        f"<a href='{escape(path, quote=True)}' class='{'active' if current_title == page_title else ''}'>{escape(label)}</a>"
        for label, path, current_title in links
    )


def performance_help_modal(sections: Mapping[str, str]) -> str:
    quickstart = str(sections.get("help-quickstart", ""))
    sampling = str(sections.get("help-sampling", ""))
    analysis = str(sections.get("help-analysis", ""))
    return (
        "<div id='performance-help-modal-root'>"
        "<div id='performance-help-modal' class='performance-help-modal' aria-hidden='true'>"
        "<div class='performance-help-backdrop' data-performance-help-close='1'></div>"
        "<div class='performance-help-dialog'>"
        "<div class='performance-help-dialog-header'>"
        "<h3 id='performance-help-title'>帮助说明</h3>"
        "<button type='button' class='performance-help-close' data-performance-help-close='1' aria-label='关闭弹窗'>x</button>"
        "</div>"
        "<div id='performance-help-content' class='performance-help-content'></div>"
        "</div>"
        "</div>"
        "<div id='help-quickstart-template' class='performance-help-template'>"
        + quickstart
        + "</div>"
        "<div id='help-sampling-template' class='performance-help-template'>"
        + sampling
        + "</div>"
        "<div id='help-analysis-template' class='performance-help-template'>"
        + analysis
        + "</div>"
        "</div>"
    )


def _metric_value_class(value: Any) -> str:
    if isinstance(value, bool) or isinstance(value, int | float):
        return "value"
    text = str(value)
    classes = ["value", "metric-text"]
    if len(text) > 12:
        classes.append("metric-compact")
    return " ".join(classes)


def metric_card(label: Any, value: Any, *, tone: str = "") -> str:
    tone_class = f" metric-{tone}" if tone else ""
    return (
        f"<article class='metric{tone_class}'>"
        f"<div class='label'>{escape(str(label))}</div>"
        f"<div class='{_metric_value_class(value)}'>{escape(str(value))}</div>"
        "</article>"
    )


def metric_grid(items: list[tuple[str, Any]], *, class_name: str = "grid") -> str:
    return f"<section class='{escape(class_name, quote=True)}'>" + "".join(
        metric_card(label, value)
        for label, value in items
    ) + "</section>"


def section(title: str, blocks: list[str], *, section_id: str | None = None) -> str:
    id_attr = f" id='{escape(section_id, quote=True)}'" if section_id else ""
    return f"<section{id_attr} class='panel'><h2>{escape(title)}</h2>{''.join(blocks)}</section>"


def compact_details(title: str, body: str) -> str:
    return (
        "<details class='compact-details'><summary>"
        + escape(title)
        + "</summary><div>"
        + body
        + "</div></details>"
    )


def notice(message: str, *, tone: str = "info") -> str:
    class_name = "notice"
    if tone == "danger":
        class_name = "notice danger"
    elif tone == "warning":
        class_name = "notice warning"
    return f"<div class='{class_name}'>{message}</div>"


def artifact_links(title: str, items: list[tuple[str, Any]]) -> str:
    links = [inline_link(label, path) for label, path in items if str(path or "").strip()]
    if not links:
        return ""
    return (
        "<div class='cards'><article class='card stack'>"
        f"<div class='meta'>{escape(title)}</div>"
        f"<div>{' / '.join(links)}</div>"
        "</article></div>"
    )


def route_link(label: str, path: Any) -> str:
    raw = str(path or "").strip()
    if not raw:
        return escape(label)
    return f"<a href='{escape(raw, quote=True)}'>{escape(label)}</a>"


def inline_link(label: str, path: Any) -> str:
    raw = str(path or "").strip()
    if not raw:
        return escape(label)
    return (
        f"<a href='/admission/view?path={quote(raw, safe='')}' target='_blank' rel='noopener noreferrer'>"
        f"{escape(label)}</a>"
    )


def sync_hint(sync_payload: dict[str, Any] | None) -> str:
    if not sync_payload:
        return "设备信息来自当前持久化快照。需要刷新时，可在 URL 后追加 ?sync_devices=1。"
    return (
        "本次页面已经同步设备注册表："
        f"scanned={sync_payload.get('scanned_count', 0)}, "
        f"updated={sync_payload.get('updated_count', 0)}, "
        f"offline={sync_payload.get('marked_offline_count', 0)}"
    )


def json_api_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return notice("当前没有可展示的 API 入口。")
    descriptions = {
        "/api/platform": "平台模式、共享入口、就绪状态和 API 清单",
        "/api/platform-health": "平台自监控快照，持续沉淀 runner、ADB、任务、证据抓取和 outbox 健康指标",
        "/api/doctor": "总诊断入口，检查 Python、ADB、设备、runtime、Web、监控 backend 和 outbox webhook",
        "/api/users": "统一用户目录，只读展示 profile/actor 与外部身份映射",
        "/api/responsibility": "跨系统责任同步视图，汇总 issue/admission/defect/release 责任字段",
        "/api/device-pools": "设备池治理视图，按 group/team/tag 汇总可调度设备和不可调度原因",
        "/api/manifest": "正式 API manifest，汇总读写端点、响应边界和回调合同",
        "/api/openapi.json": "OpenAPI 风格描述，供共享入口和外部系统对接参考",
        "/api/home": "首页总览聚合数据",
        "/api/tasks": "任务和 run 列表",
        "/api/long-run-templates": "长稳运行模板默认值、可覆盖参数和计划预览",
        "/api/performance": "最近监控快照聚合，并说明性能 risk item 的 threshold_source / matched_scope / threshold_detail 字段",
        "/api/integration": "集成 outbox 总览、worker 与 webhook 状态",
        "/api/issues": "问题中心聚合和协作数据；高级异常会透出 evidence_signals / confirmation_level，初步归因会兼容展示 direction / confidence / matched_rule_ids / evidence_summary / recommended_next_steps",
        "/api/runner": "巡检 runner 状态和日报周报",
        "/api/goldens": "Golden Suite 总览",
        "/api/admission": "准入中心总览",
        "/api/admission/cases": "稳定 AdmissionCase 合同与列表入口",
        "/api/admission/reports/<baseline_key>": "正式准入报告 JSON，包含最终结论、风险等级、证据引用、外部回写和建议动作",
        "/api/rules": "规则配置中心，只读展示当前版本、校验状态、可编辑字段、风险提示和预览入口",
        "/api/integration/outbox": "集成 outbox 事件和投递状态",
        "/ready": "团队入口 ready 检查和关键服务就绪状态",
        "/health": "服务健康检查",
    }
    cards = []
    for item in items:
        path = str(item.get("path", "") or "")
        label = str(item.get("label", path) or path)
        description = descriptions.get(path, "当前接口没有额外说明。")
        cards.append(
            "<article class='card stack'>"
            f"<h3>{escape(label)}</h3>"
            f"<div class='meta'>{escape(description)}</div>"
            f"<div><span class='mono'>{escape(path)}</span></div>"
            f"<div>{route_link('打开 JSON', path)}</div>"
            "</article>"
        )
    return "<div class='cards'>" + "".join(cards) + "</div>"


def json_api_usage_cards() -> str:
    return (
        "<div class='cards'>"
        "<article class='card stack'>"
        "<h3>浏览器里看</h3>"
        "<div>先从这个页面点进具体接口，再决定要不要继续打开详情接口或文件产物。</div>"
        "<div><a href='/api/platform'>平台 JSON</a> / <a href='/api/users'>用户目录</a> / <a href='/api/responsibility'>责任同步</a> / <a href='/api/device-pools'>设备池 JSON</a> / <a href='/api/manifest'>API Manifest</a> / <a href='/api/openapi.json'>OpenAPI</a> / <a href='/api/home'>首页 JSON</a> / <a href='/api/tasks'>任务 JSON</a> / <a href='/api/long-run-templates'>长稳模板 JSON</a> / <a href='/api/performance'>性能 JSON</a> / <a href='/api/rules'>规则 JSON</a> / <a href='/api/integration'>集成 JSON</a></div>"
        "</article>"
        "<article class='card stack'>"
        "<h3>命令行里取</h3>"
        "<pre class='mono'>"
        + escape(
            "\n".join(
                [
                    "curl http://127.0.0.1:8030/api/platform",
                    "curl http://127.0.0.1:8030/api/doctor",
                    "curl http://127.0.0.1:8030/api/users",
                    "curl http://127.0.0.1:8030/api/responsibility",
                    "curl http://127.0.0.1:8030/api/device-pools",
                    "curl http://127.0.0.1:8030/api/manifest",
                    "curl http://127.0.0.1:8030/api/openapi.json",
                    "curl http://127.0.0.1:8030/api/home",
                    "curl http://127.0.0.1:8030/api/long-run-templates",
                    "curl http://127.0.0.1:8030/api/performance",
                    "curl http://127.0.0.1:8030/api/admission/reports/<baseline_key>",
                    "curl http://127.0.0.1:8030/api/rules",
                    "curl http://127.0.0.1:8030/ready",
                    "curl http://127.0.0.1:8030/health",
                ]
            )
        )
        + "</pre>"
        "<div class='meta'>脚本和自动化继续直接访问 /api/*，不需要经过这个导航页。</div>"
        "<div class='meta'>高级异常证据字段：问题聚合优先看 evidence_signals / confirmation_level；初步归因优先看 direction / confidence_score / matched_rule_ids / evidence_summary / recommended_next_steps；性能风险优先看 threshold_source / matched_scope / threshold_detail。</div>"
        "</article>"
        "</div>"
    )

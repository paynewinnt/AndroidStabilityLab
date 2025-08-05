from __future__ import annotations

from .application_common import *


class ApplicationHelpPagesMixin:
    def _page_help_sections(
        self,
        page_title: str,
        summary: Mapping[str, Any] | None = None,
    ) -> tuple[list[tuple[str, str]], dict[str, str]]:
        summary = dict(summary or {})
        if page_title == "性能采样":
            return (
                [
                    ("help-quickstart", "三步上手"),
                    ("help-sampling", "怎么采样"),
                    ("help-analysis", "怎么分析"),
                ],
                {
                    "help-quickstart": self._performance_quickstart_cards(summary),
                    "help-sampling": self._performance_sampling_guide(),
                    "help-analysis": self._performance_analysis_guide(),
                },
            )
        if page_title == "Web 首页":
            buttons = [
                ("help-quickstart", "先看什么"),
                ("help-sampling", "怎么下钻"),
                ("help-analysis", "怎么分析"),
            ]
            return buttons, {
                "help-quickstart": self._help_card(
                    "1. 首页起点",
                    [
                        "先看设备状态、Runner 状态、最近失败 run，以及本次可关注的问题/基线。",
                        "如果首页没有健康信号，优先回到任务大厅查当前排队与执行。",
                    ],
                    links=[("任务大厅", "/tasks"), ("问题中心", "/issues"), ("准入中心", "/admission")],
                ),
                "help-sampling": self._help_card(
                    "2. 怎么补充上下文",
                    [
                        "快速补齐上下文的最快路径：任务大厅查看任务+run，问题中心确认近期告警。",
                        "再回到首页核对 Runner 运行节奏是否恢复。",
                    ],
                    code=[
                        "curl http://127.0.0.1:8030/api/home",
                        "curl http://127.0.0.1:8030/api/runner",
                    ],
                ),
                "help-analysis": self._help_card(
                    "3. 怎么做判断",
                    [
                        "先判断本班是否可追溯：设备、runner、告警和 run 是否都在预期区间。",
                        "再决定是否立刻暂停后续执行或标记为待确认。",
                    ],
                    links=[("后台巡检", "/runner"), ("任务 JSON", "/api/tasks"), ("Run JSON", "/api/tasks")],
                ),
            }
        if page_title == "平台说明":
            return (
                [
                    ("help-quickstart", "先看边界"),
                    ("help-sampling", "入口清单"),
                    ("help-analysis", "部署判断"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先确认平台边界",
                        [
                            "先看当前是本地值班模式还是团队共享入口模式。",
                            "再确认写操作是否要求服务端解析 identity、session 和审计事件。",
                        ],
                        links=[("平台说明", "/platform"), ("诊断中心", "/doctor"), ("接口中心", "/json-api")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 可用入口怎么查",
                        [
                            "页面入口用于人工查看和操作，JSON API 用于脚本读取。",
                            "如果要接外部系统，先看集成 Outbox，而不是直接读页面 HTML。",
                        ],
                        links=[("任务大厅", "/tasks"), ("集成 Outbox", "/integration"), ("API Manifest", "/api/manifest")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么判断部署是否可用",
                        [
                            "先看 readiness、health、页面数和 API 数是否符合预期。",
                            "如部署模式或身份边界异常，优先到诊断中心排查配置与 runtime 路径。",
                        ],
                        code=[
                            "curl http://127.0.0.1:8030/ready",
                            "curl http://127.0.0.1:8030/health",
                        ],
                    ),
                },
            )
        if page_title == "诊断中心":
            return (
                [
                    ("help-quickstart", "先跑诊断"),
                    ("help-sampling", "查设备链路"),
                    ("help-analysis", "定位层级"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看总状态",
                        [
                            "先确认 Python、ADB、runtime、配置、端口和 webhook 哪一类失败。",
                            "默认诊断不发送外部消息；只有显式检查 webhook 时才会发诊断 ping。",
                        ],
                        links=[("诊断中心", "/doctor"), ("设备池", "/device-pools"), ("集成 Outbox", "/integration")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么查设备",
                        [
                            "输入 device_id 后做单设备深度诊断，确认授权、shell、perfetto 和临时目录权限。",
                            "无线 ADB 问题优先确认 host:port 是否可达，再刷新设备池。",
                        ],
                        code=[
                            "python -m stability.cli doctor --device-id <device_id> --package-name <package>",
                            "adb devices",
                        ],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么定位问题层级",
                        [
                            "fail 是必须处理项，warn 是可能影响采集或投递的风险项。",
                            "先修环境/设备，再修任务或准入，不要直接从页面现象判断业务失败。",
                        ],
                        links=[("任务大厅", "/tasks"), ("性能采样", "/performance"), ("Runner", "/runner")],
                    ),
                },
            )
        if page_title == "设备池":
            return (
                [
                    ("help-quickstart", "先刷新设备"),
                    ("help-sampling", "连接无线 ADB"),
                    ("help-analysis", "标记与调度"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先刷新设备状态",
                        [
                            "点击刷新 ADB 设备后，再看哪些设备 online、schedulable、blocked。",
                            "如果终端 adb devices 可见但页面不可调度，先刷新设备池再看不可调度原因。",
                        ],
                        links=[("设备池", "/device-pools"), ("诊断中心", "/doctor"), ("任务大厅", "/tasks")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么连接无线 ADB",
                        [
                            "手机显示 host:port 后，在页面填入 IP:端口并点击连接并刷新。",
                            "如果提示 no route to host，通常是手机重启、无线调试端口变化或电脑手机不在同一网络。",
                        ],
                        code=[
                            "adb connect <ip>:<port>",
                            "adb devices",
                        ],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么做设备标记",
                        [
                            "在每个设备卡片里编辑 group、team、tag，避免手动复制 device_id。",
                            "创建任务时优先选择可调度设备；blocked 设备先按原因处理。",
                        ],
                        links=[("创建任务", "/tasks"), ("设备 JSON", "/api/device-pools")],
                    ),
                },
            )
        if page_title == "长稳运行模板":
            return (
                [
                    ("help-quickstart", "先选模板"),
                    ("help-sampling", "配置轮转"),
                    ("help-analysis", "接入 Runner"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看模板适用场景",
                        [
                            "先确认模板是冷启动、Monkey、前后台、重启、安装卸载还是自定义任务。",
                            "再看默认参数和可覆盖字段，避免把短测模板当成长稳模板。",
                        ],
                        links=[("长稳模板", "/long-run-templates"), ("任务大厅", "/tasks")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么配置轮转",
                        [
                            "长稳任务需要明确主备设备、间隔、并发和补位策略。",
                            "只看模板不会自动生效，必须通过任务大厅或无人值守配置显式创建。",
                        ],
                        links=[("创建长稳任务", "/tasks"), ("设备池", "/device-pools")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么确认跑起来",
                        [
                            "创建后到巡检状态确认 runner 心跳和最近 patrol。",
                            "再回任务大厅或性能采样页检查 Run 与监控快照。",
                        ],
                        links=[("巡检状态", "/runner"), ("性能采样", "/performance"), ("任务大厅", "/tasks")],
                    ),
                },
            )
        if page_title == "任务大厅":
            buttons = [
                ("help-quickstart", "先选任务"),
                ("help-sampling", "任务怎么跑"),
                ("help-analysis", "怎么下钻"),
            ]
            return buttons, {
                "help-quickstart": self._help_card(
                    "1. 快速入场",
                    [
                        "先确认要重跑或复验的任务定义是否在列表可见。",
                        "关注最近 Run 数、失败率和有无 Trace 的 run。",
                    ],
                    links=[("任务列表", "/tasks"), ("最新采样", "/performance"), ("Run 列表", "/tasks")],
                ),
                "help-sampling": self._help_card(
                    "2. 如何触发新数据",
                    [
                        "执行任务后会返回新的 run，再到列表里找对应 run_id。",
                        "如要做监控验证，可在执行参数中带 monitoring backend。",
                    ],
                    code=[
                        "./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend solox",
                        "./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend perfetto",
                    ],
                ),
                "help-analysis": self._help_card(
                    "3. 怎么排查 run",
                    [
                        "先点 Run 详情看 Monitoring Overview 和 Instance 维度。",
                        "如发现异常，优先把链接记录到 Run 详情中的 JSON / trace 位置。",
                    ],
                    links=[("性能采样", "/performance"), ("Run 详情", "/runs"), ("JSON API", "/api/tasks")],
                ),
            }
        if page_title == "Run 详情":
            return (
                [
                    ("help-quickstart", "怎么找 Run"),
                    ("help-sampling", "怎么看监控"),
                    ("help-analysis", "下钻顺序"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. Run 上手",
                        [
                            "确认 run_id 对应的是本次执行实例（状态、创建/结束时间、任务名）。",
                            "优先核对监控样本与 Trace 数。",
                        ],
                        links=[("返回任务大厅", "/tasks"), ("返回任务详情", "/tasks")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 采样解读",
                        [
                            "先读 Monitoring Overview 的 summary_line，确认是否采到 baseline 与关键指标。",
                            "再看 snapshot 与 trace 是否可用于 trace 级分析。",
                        ],
                        links=[("性能采样", "/performance"), ("JSON 详情", "/api/tasks")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 分析顺序",
                        [
                            "建议先看执行实例卡片中的 backend/key metrics。",
                            "确认异常后到任务大厅追该 run 的前后文，是否是偶发。",
                        ],
                        links=[("任务大厅", "/tasks"), ("问题中心", "/issues"), ("准入中心", "/admission")],
                    ),
                },
            )
        if page_title == "问题中心":
            return (
                [
                    ("help-quickstart", "问题上手"),
                    ("help-sampling", "怎么认领"),
                    ("help-analysis", "协作复盘"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看 Top Issue",
                        [
                            "优先看 Critical/High 与最近发生时间。",
                            "从聚合统计确认是否是同源问题。",
                        ],
                        links=[("问题中心", "/issues"), ("任务大厅", "/tasks"), ("准入中心", "/admission")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么认领",
                        [
                            "在详情页认领后可继续留痕追踪状态。",
                            "有协作动作后再看 action 的角色来源和时间。",
                        ],
                        links=[("问题详情", "/issues"), ("协作 API", "/api/issues")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么复盘",
                        [
                            "建议先用 run_id 追到对应执行上下文，再回到 run 详情比对趋势。",
                            "同一问题未闭环前，可用 notice 方式保留讨论记录。",
                        ],
                        links=[("运行状态", "/tasks"), ("Run 详情", "/tasks")],
                    ),
                },
            )
        if page_title == "后台巡检状态":
            return (
                [
                    ("help-quickstart", "先看 Runner"),
                    ("help-sampling", "如何恢复"),
                    ("help-analysis", "巡检解释"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看状态",
                        [
                            "先看 Runner 状态、锁状态、Cycle 与心跳年龄。",
                            "心跳断更时先判断是否有悬挂实例。",
                        ],
                        links=[("巡检状态", "/runner"), ("后台任务", "/runner"), ("首页", "/")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 如何补齐巡检",
                        [
                            "如果未见心跳，按 runner 脚本启动方式重跑；看最近心跳关联定位阻塞。",
                            "先执行启动命令再刷新页面确认状态变更。",
                        ],
                        meta="本页为巡检入口，不替代运维脚本执行。",
                    ),
                    "help-analysis": self._help_card(
                        "3. 重点解读",
                        [
                            "把失败率、掉线率、恢复率作为本班质量是否可放行的辅助指标。",
                            "隔离设备数上升通常是排障入口，不一定是主因。",
                        ],
                        links=[("每日报表", "/runner"), ("周报关联", "/runner"), ("API", "/api/runner")],
                    ),
                },
            )
        if page_title == "集成 Outbox":
            return (
                [
                    ("help-quickstart", "先看队列"),
                    ("help-sampling", "怎么投递"),
                    ("help-analysis", "失败处理"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看投递状态",
                        [
                            "先看 pending、retry、delivered、dead-letter 和告警事件数量。",
                            "确认 webhook 已注册后，再触发投递或 worker。",
                        ],
                        links=[("集成 Outbox", "/integration"), ("诊断中心", "/doctor"), ("准入中心", "/admission")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么触发投递",
                        [
                            "优先用页面里的单轮投递、worker 或 replay 入口，不直接改 outbox 文件。",
                            "联调 IM/CI 前先确认 endpoint、签名密钥和 receipt 是否正常。",
                        ],
                        code=[
                            "python -m stability.cli run-delivery-worker --help",
                            "python -m stability.cli replay-outbox-dead-letters --help",
                        ],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么处理失败",
                        [
                            "重试中先看 last_error 和 next_retry_at，死信再做 replay。",
                            "如果失败放大，先暂停 worker，确认签名、网络和消费方返回码。",
                        ],
                        links=[("Outbox JSON", "/api/integration"), ("平台说明", "/platform")],
                    ),
                },
            )
        if page_title == "规则中心":
            return (
                [
                    ("help-quickstart", "先看规则"),
                    ("help-sampling", "预览变更"),
                    ("help-analysis", "审计准入"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看规则状态",
                        [
                            "先确认当前版本、校验结果、错误/警告数量和可编辑字段。",
                            "本页默认只读，不直接绕过审计写配置。",
                        ],
                        links=[("规则中心", "/rules"), ("准入中心", "/admission"), ("Golden Suite", "/goldens")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么预览变更",
                        [
                            "用 query 参数预览候选规则，不直接覆盖正式配置。",
                            "预览后再走 diff、review、golden replay 和 baseline audit。",
                        ],
                        code=[
                            "curl 'http://127.0.0.1:8030/api/rules?set.version=candidate-v2'",
                        ],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么判断能不能入库",
                        [
                            "规则变更要看校验、Golden 差异、baseline 审计和 AdmissionCase 结论。",
                            "有风险提示时，不建议只凭页面预览结果放行。",
                        ],
                        links=[("Golden Diff", "/goldens/diff"), ("准入中心", "/admission"), ("API", "/api/rules")],
                    ),
                },
            )
        if page_title == "Golden Suite":
            return (
                [
                    ("help-quickstart", "先看 Suite"),
                    ("help-sampling", "怎么比对"),
                    ("help-analysis", "怎么验证"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看 Case",
                        [
                            "先看 suite 概览中的 layer 和 issue_type 分布。",
                            "按你的关注方向挑一个 case 继续下钻。",
                        ],
                        links=[("Golden Suite", "/goldens"), ("案例详情", "/goldens"), ("Diff", "/goldens/diff")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么比对",
                        [
                            "用 Diff 页指定左/右版本，聚焦 modified/added/removed。",
                            "结合字段层次逐步确认是否影响准入。",
                        ],
                        links=[("打开 Diff", "/goldens/diff"), ("运行任务", "/tasks"), ("API", "/api/goldens")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么验证",
                        [
                            "对比后的 case 字段与 baseline 关联性最直接。",
                            "确认 case_id 与 run 运行上下文是否一致。",
                        ],
                        links=[("Golden Case", "/goldens"), ("准入中心", "/admission"), ("任务大厅", "/tasks")],
                    ),
                },
            )
        if page_title == "Golden Suite Diff":
            return (
                [
                    ("help-quickstart", "先选对比"),
                    ("help-sampling", "设置筛选"),
                    ("help-analysis", "读变更"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先选对比版本",
                        [
                            "先确认 left/right 版本，差异才有明确可比性。",
                            "优先对近周期版本做首轮验收。",
                        ],
                        links=[("Golden Suite", "/goldens"), ("Diff", "/goldens/diff"), ("首页", "/")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 怎么取样本",
                        [
                            "按 changed_field / change_type 先收敛变更范围。",
                            "减少无关差异，先看字段关键路径。",
                        ],
                        links=[("查看 Diff", "/goldens/diff"), ("API", "/api/goldens")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 怎么解读",
                        [
                            "Modified 通常是高优先级变更，优先确认是否影响质量门禁。",
                            "Removed/Added 需结合 expectation 看是否引入回归风险。",
                        ],
                        links=[("准入中心", "/admission"), ("任务大厅", "/tasks"), ("问题中心", "/issues")],
                    ),
                },
            )
        if page_title == "准入中心":
            return (
                [
                    ("help-quickstart", "先看中心"),
                    ("help-sampling", "质量门禁"),
                    ("help-analysis", "人工覆盖"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看总体",
                        [
                            "先看自动 Fail、最终 Fail 与人工覆盖比例。",
                            "关注是否已有未确认的新风控项。",
                        ],
                        links=[("准入中心", "/admission"), ("准入详情", "/admission"), ("任务大厅", "/tasks")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 质量门禁解读",
                        [
                            "关注规则通过情况、风险数、性能风险数和覆盖不足指标。",
                            "指标异常要优先回到具体 case。",
                        ],
                        links=[("质量门禁", "/admission"), ("性能采样", "/performance"), ("报告", "/api/admission")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 人工确认路径",
                        [
                            "人工覆盖记录影响最终意见，确认后再回传状态。",
                            "变更覆盖前先记录证据与上下文。",
                        ],
                        code=[
                            "curl http://127.0.0.1:8030/api/admission",
                            "curl http://127.0.0.1:8030/api/admission?case_id=<case_id>",
                        ],
                    ),
                },
            )
        if page_title.startswith("准入详情 · "):
            return (
                [
                    ("help-quickstart", "先看结论"),
                    ("help-sampling", "看依据"),
                    ("help-analysis", "人工操作"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先看结论",
                        [
                            "先看自动结论、最终结论、人工覆盖状态。",
                            "结合 Top Issue 与回归结论判断该 case 的风险边界。",
                        ],
                        links=[("准入中心", "/admission"), ("返回", "/admission")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 看依据",
                        [
                            "逐项核对执行摘要、风险项、性能风险和覆盖不足。",
                            "再看 latest audit 与 golden suite 支撑该 case。",
                        ],
                        links=[("执行汇总", "/admission"), ("Latest Audit", "/api/admission"), ("Golden", "/goldens")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 人工操作",
                        [
                            "如需覆盖，需要结合当前任务阶段和回归影响确认最终意见。",
                            "确认后刷新页面以观察 action 记录变化。",
                        ],
                        meta="页面包含操作入口时，优先使用页面内表单提交。",
                    ),
                },
            )
        if page_title == "JSON API" or "接口" in page_title:
            return (
                [
                    ("help-quickstart", "先选接口"),
                    ("help-sampling", "直接看原始"),
                    ("help-analysis", "命令行化"),
                ],
                {
                    "help-quickstart": self._help_card(
                        "1. 先选接口",
                        [
                            "先从常用接口跳转到对应 JSON，避免一次看完整屏。",
                            "每个入口默认是只读导航。",
                        ],
                        links=[("首页", "/"), ("任务 JSON", "/api/tasks"), ("性能 JSON", "/api/performance")],
                    ),
                    "help-sampling": self._help_card(
                        "2. 直接看原始",
                        [
                            "点进目标接口后看返回结构，判断是否包含期望字段。",
                            "若缺字段，通常是 payload 聚合口径变更，不一定是数据异常。",
                        ],
                        links=[("问题 JSON", "/api/issues"), ("准入 JSON", "/api/admission"), ("Runner JSON", "/api/runner")],
                    ),
                    "help-analysis": self._help_card(
                        "3. 命令行化",
                        [
                            "自动化优先用接口 JSON，便于把结果落盘和比对。",
                            "浏览器仅用于快速确认，不作为唯一证据来源。",
                        ],
                        code=[
                            "curl http://127.0.0.1:8030/api/home",
                            "curl http://127.0.0.1:8030/api/tasks",
                        ],
                    ),
                },
            )
        buttons = [
            ("help-quickstart", "三步上手"),
            ("help-sampling", "怎么采样"),
            ("help-analysis", "怎么分析"),
        ]
        return buttons, self._help_default_sections(page_title)

    @staticmethod
    def _sidebar_nav(page_title: str) -> str:
        return portal_renderers.sidebar_nav(page_title)

    def _json_api_cards(self, items: list[dict[str, Any]]) -> str:
        return portal_renderers.json_api_cards(items)

    def _json_api_usage_cards(self) -> str:
        return portal_renderers.json_api_usage_cards()

    def _performance_help_modal(self, sections: Mapping[str, str]) -> str:
        return portal_renderers.performance_help_modal(sections)

    @staticmethod
    def _metric_grid(items: list[tuple[str, Any]]) -> str:
        return portal_renderers.metric_grid(items)

    @staticmethod
    def _section(title: str, blocks: list[str], *, section_id: str | None = None) -> str:
        return portal_renderers.section(title, blocks, section_id=section_id)

    @staticmethod
    def _compact_details(title: str, body: str) -> str:
        return portal_renderers.compact_details(title, body)

    @staticmethod
    def _notice(message: str, *, tone: str = "info") -> str:
        return portal_renderers.notice(message, tone=tone)

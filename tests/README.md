Run the unit tests from the repository root with:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

Current local baseline:

```text
Ran 466 tests

OK
```

The current baseline covers issue artifact capture and one end-to-end execution path that verifies issue detection, artifact persistence, and report rendering together. The issue evidence collector now also supports type-aware best-effort extended evidence capture for `dropbox`、`dumpsys meminfo`、`dumpsys SurfaceFlinger`、`screenshot`、`input events` and existing `Perfetto trace` files, and will attach those artifacts into the same issue evidence directory when the current issue type matches the configured capture policy. Display/system critical issues also fold captured artifact sources back into `evidence_signals / matched_sources / confirmation_level`.

`execute-run` 现在支持 `--retry-count N`，会只对 `device_offline`、`startup_timeout`、`adb transport` 类可恢复失败做最多 `N` 次额外重试，并在重试前或异常中断后对目标包做 best-effort `am force-stop` 清理。报告中会新增 `Execution Attempts` 与 `Cleanup` 小节，并记录每次尝试是否可重试及其分类。

查询类 CLI 已补齐：`python -m stability.cli list-devices/show-device/list-tasks/show-task/list-runs/show-run` 都可直接查询持久化对象。其中 `list-devices` 和 `show-device` 支持两种同步方式：`--sync` 做全量设备表刷新，`list-devices --sync-device SERIAL` / `show-device --sync-target-only` 只刷新目标设备，避免查询单设备时做整表同步。

`V3` 阶段 1 的最小无人值守后台闭环也已接上：
- `python -m stability.cli configure-unattended-task --task-id ... --interval-minutes ...`：给已有任务补充周期配置、主设备、候补设备、失败隔离阈值、长稳轮转策略和最近轮次/设备窗口保留数
- `python -m stability.cli list-unattended-tasks / show-unattended-task --task-id ...`：查看当前无人值守任务的 `next_run_at / due / latest_summary / recent_rounds`
- `python -m stability.cli run-unattended-round --task-id ...`：立即触发一轮后台执行
- `python -m stability.cli patrol-unattended-tasks`：批量执行到期任务，并输出失败率、掉线率、恢复成功率、隔离设备数等最小巡检摘要
- `python -m stability.cli run-unattended-patrol-runner --interval-seconds 60 --max-iterations 10`：以最小定时后台 loop 周期性执行 patrol；`--max-iterations 0` 时会持续运行直到手动中断
- `python -m stability.cli build-unattended-daily-report [--task-id ...] [--report-date YYYY-MM-DD]`：基于已保留的无人值守轮次历史，生成一份日级执行摘要
- `python -m stability.cli build-unattended-weekly-report [--task-id ...] [--report-date YYYY-MM-DD]`：基于已保留的无人值守轮次历史，生成一份周级执行摘要

当前无人值守能力已覆盖：
- 周期触发：按 `interval_minutes` 维护 `next_run_at`
- 轮次记录：为每轮保存 `recent_rounds` 和最近运行摘要
- 更完整长稳轮转：无人值守任务现在支持 `fixed / round_robin` 两种主设备轮转策略、`every_round / failure_only` 两种轮转推进策略，并持久化 `rotation_cursor / rotation_advance_count / recent_device_windows / long_run_summary`
- 候补设备补位：主设备不可调度时自动从候补池或空闲设备池补位
- 设备隔离：连续失败达到阈值后自动标记为 `quarantined`
- 隔离后自动恢复探测：`patrol-unattended-tasks` 会对 `quarantined` 设备做节流探测；设备重新上线后会自动解除隔离，并把探测次数、跳过次数、恢复设备数写入巡检摘要
- 最小定时 patrol runner：可按秒级间隔循环调用 `patrol-unattended-tasks`，输出每轮 patrol 摘要和最终停止原因，便于先接系统调度或 supervisor
- 单实例锁与运行心跳：runner 会在 `runtime/unattended_runner/` 下维护 `runner.lock` 和 `runner_status.json`；已有活动实例时会拒绝第二实例，异常或正常退出后会释放锁并更新最新心跳
- 自动日报：runner 现在会在每轮 patrol 后自动刷新 `runtime/unattended_runner/daily_reports/<YYYY-MM-DD>/report.json + summary.md`，同时把 latest daily report 摘要写入心跳文件
- 最小周报：`build-unattended-weekly-report` 现已可按周聚合轮次历史，runner 也会在每轮 patrol 后自动刷新 `runtime/unattended_runner/weekly_reports/<YYYY-Www>/report.json + summary.md`，同时把 latest weekly report 摘要写入心跳文件
- Web 巡检状态页：`/runner` 和 `/api/runner` 会直接展示 runner 的锁状态、运行心跳、latest daily report / latest weekly report 摘要、最近一轮 patrol 摘要和状态路径，方便先做值班视角排查
- 最近 patrol 历史列表：`runner_status.json` 现在会保留有限长度的 `recent_patrols`，`/runner` 和 `/api/runner` 可直接回看最近几轮 patrol 的执行/失败/掉线/恢复/隔离摘要
- 失败轮次快速过滤：`/runner` 和 `/api/runner` 现支持按 `全部 / 失败轮次 / 掉线轮次 / 隔离轮次` 快速筛选最近 patrol 历史，便于值班时直接聚焦异常轮次
- 异常轮次详情展开：`/runner` 页面里的异常 patrol 轮次现在支持直接展开查看 `task_count / due_task_count / skipped_task_count / probe_attempts / probe_recovered` 等摘要，不必先回原始 JSON
- 异常轮次一键跳转：`/runner` 页顶部现提供 `一键看失败轮次 / 掉线轮次 / 隔离轮次` 快捷入口，可直接跳到对应过滤结果
- 最新心跳关联提示：`/runner` 页顶部现会直接判断“最新心跳对应的最新 patrol 是否异常”，并在异常时给出跳到失败/掉线/隔离过滤结果的快捷入口
- 任务影响范围提示：`/runner` 页顶部的最新心跳关联提示现在会同时带出 `task_count / due_task_count / executed_task_count / skipped_task_count`，方便先判断异常是局部抖动还是已经影响整轮巡检
- 异常严重度分层：`/runner` 页现在会按 `正常 / 中 / 高 / 严重` 给最新 patrol 和最近 patrol 历史做分层；其中掉线波动记为 `中`，出现失败记为 `高`，出现隔离设备或“失败伴随任务跳过”记为 `严重`
- 严重度过滤：`/runner` 和 `/api/runner` 现在支持 `severity_filter=medium|high|critical`，并且可以和现有 `patrol_filter` 叠加使用，方便先只看高优先级异常轮次
- 首页巡检摘要卡：首页会直接前置展示 runner 的 `status / lock_state / heartbeat age / cycle_count / latest daily report 摘要 / latest weekly report 摘要 / 最近一轮 patrol 摘要`，不用先下钻到 `/runner`，并对 `stale / missing / failed` 以及“latest daily report 已出现失败轮次/隔离设备”这类异常态做高亮提示、操作建议和可直接点击的动作入口

能力状态测试口径：

| 能力 | 测试可证明 | 测试不能证明 |
| --- | --- | --- |
| IM/飞书 | 本地 mock/smoke 能证明平台侧 webhook 注册、payload、header、worker、receipt 和 outbox 观测可用 | 真实 IM endpoint 24 小时稳定、生产群噪声可接受、接收方验签/幂等/限流均已验收 |
| SSO/身份 | 单测和 Web smoke 能证明受信 header claims、本地 session、写操作审计、只读用户目录/责任检索的最小路径 | 完整企业级 OIDC/LDAP/SSO、独立 IAM、多租户数据隔离和复杂组织权限 |
| 设备调度 | runner 和无人值守 smoke 能证明本地轮转、候补补位、隔离、恢复探测、日报/周报摘要链路 | 团队级设备预约、配额、审批、排班、维护窗口和跨团队设备调度平台 |
| 规则在线发布 | 规则相关测试能证明本地规则校验、diff、回放、评审、golden suite 和基线审计 | 在线保存、发布、审批、灰度和回滚的完整规则发布流程 |

`V3` 的最小 Web 主入口已经补上：`python -m stability.cli serve-web --host 127.0.0.1 --port 8030` 会启动一个无额外依赖的本地门户，直接提供 8 个页面 `/`、`/tasks`、`/performance`、`/issues`、`/runner`、`/goldens`、`/admission`、`/json-api`，同时暴露 `/api/home`、`/api/tasks`、`/api/performance`、`/api/issues`、`/api/runner`、`/api/goldens`、`/api/admission`、`/api/admission/cases`、`/api/integration/outbox`、`/health` 这几条 JSON 端点。这个入口当前直接复用持久化 service bundle，把设备摘要、任务/Run 历史、最近监控快照、Top Issue、runner 巡检状态、正式 golden suite 样本库和规则准入基线 latest 审计聚合到一个浏览器入口里；现在 `/goldens` 和 `/api/goldens` 会显式展示 golden suite 的样本清单、layer/issue_type/expectation 计数，并支持下钻到 `/goldens/case/<case_id>` 和 `/api/goldens/case/<case_id>` 展开单条 case 的 `summary / expected / baseline_rules / candidate_rules / filters / dataset`，也支持通过 `/goldens/diff` 和 `/api/goldens/diff` 只读查看两份 suite 的差异摘要、变更类型计数以及逐 case 的 `added / removed / modified / unchanged` 结果；现在 diff 页还支持 `change_type` 过滤、`changed_field` 字段级过滤和 `case_id` 搜索，并会在卡片里直接展示左右 case 的最小字段对比摘要，同时提供 `baseline_rules / candidate_rules / filters / expected` 四个关键块的折叠式摘要，再继续跳到左右两侧 case 详情；`/runner` 和 `/api/runner` 则会直接展示 patrol runner 的锁状态、运行心跳、最近一轮巡检摘要和状态路径；`/performance` 和 `/api/performance` 会把最近执行实例已落盘的 monitoring snapshot、backend、关键指标和 trace/snapshot 链接收口到同一页；同时 `/admission`、`/api/admission`、`/api/admission/cases` 会显式展示基线级 `AdmissionCase` 合同、`contract_version / status / revision / case_trace / source_refs / ci_contract` 等稳定字段，并支持从准入中心下钻到 `/admission/baseline/<baseline_key>`、`/api/admission/baseline/<baseline_key>` 和 `/api/admission/cases/<baseline_key>`，直接查看单条基线的当前报告、AdmissionCase、golden suite、latest audit、comparison report、baseline history 时间线和最近版本索引；详情页顶部还会显示 `review / comparison / latest audit / golden suite` 四项状态摘要，并且四个状态块都可以点击下钻到对应 section，同时会附带缺失态/失败态的下一步操作建议，时间线支持 `action` 和 `comparison_only` 两个最小过滤参数，并且每条事件已经支持折叠详情；详情页里的报告和审计产物也已经可以通过 `/admission/view?path=...` 直接跳转打开。这里的“版本测试报告 / 准入报告”按结构化 report payload、Web/API 页面摘要和本地报告/审计/对比产物跳转验收，跨人共享仍优先使用本地部署页面、报告、JSON、HTML、Markdown 和运行产物导出，不按完整对外 PDF、邮件自动分发或多级审批流验收。

`V3` 的最小 outbox 运维面也已补上：`python -m stability.cli register-integration-webhook --name ... --url ... [--event-type ...]` 可注册一条本地 webhook 目标，`python -m stability.cli deliver-integration-outbox --webhook-name ... [--event-type ...] [--limit ...]` 可执行单轮投递，`python -m stability.cli run-integration-outbox-worker [--webhook-name ...] [--rounds ...] [--stop-when-idle]` 可按 webhook 执行多轮 delivery worker，`python -m stability.cli replay-integration-dead-letters [--event-id ...] [--event-type ...] [--execute]` 可预览或回放 dead-letter 事件。当前事件会持久化 `delivery_status / attempt_count / last_error / next_retry_at / signature / retry_backoff_seconds / dead_lettered_at / alert_status`，并通过 `/api/integration/outbox` 一起暴露 worker 配置、delivery_receipt、consumer_receipt、worker_status、幂等 key、dead-letter/retry 统计和 webhook 注册清单。平台从“单命令输出”逐步升级到“运维面”：CLI 侧提供可回放/可跑 worker 的闭环命令，Web 侧提供 `/api/integration/outbox` 的运维可观测字段，便于值班统一判断出站链路、重试压力、dead-letter 处理和回放状态。当前 transport 侧 receipt 仍是链路层 ack，consumer_receipt 依据下游响应持久化。

IM/飞书通知链路的本地 mock/smoke 可先验证平台侧能力，但不能替代真实 2 小时试运行或 24 小时联调。推荐本地先跑：

```bash
./.venv/bin/python -m unittest \
  tests.test_integration_outbox_service \
  tests.test_cli_web_integration_commands \
  -v
```

如需验证本地 HTTP mock endpoint，可按 [IM 通知真实链路长时联调 Runbook](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/docs/运维/IM通知真实链路长时联调Runbook.md) 启动临时 `127.0.0.1:9010` 接收器，再注册 `local-im-smoke` 并执行 `run-im-notify-worker --max-rounds 1`。本地 smoke 成功只能说明 `im_notify` delivery channel、`asl.im_notify.v1` payload、header、worker、receipt 和 outbox 观测面可用；真实 IM endpoint 的验签、幂等、限流、消息格式、群噪声和 24 小时稳定性仍必须按 runbook 单独验收。

飞书真实联调命令说明：

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/<token>"
export FEISHU_SIGNING_SECRET="<feishu-bot-secret>"

./.venv/bin/python -m stability.cli register-feishu-webhook \
  --name "Android Stability Lab" \
  --url "$FEISHU_WEBHOOK_URL" \
  --signing-secret "$FEISHU_SIGNING_SECRET" \
  --signature-key-id feishu-v1 \
  --secret-hint "feishu bot secret from local env, do not commit runtime" \
  --failure-policy retryable_http \
  --event-type admission_case.updated \
  --event-type admission.override_recorded \
  --event-type outbox.retry_alert \
  --created-by ops

./.venv/bin/python -m stability.cli run-feishu-notify-worker \
  --daemon \
  --webhook-name "Android Stability Lab" \
  --interval-seconds 60 \
  --limit-per-webhook 20 \
  --max-runtime-seconds 7200
```

2 小时试运行通过只能说明真实飞书 endpoint 可以进入 24 小时联调；最终完成标准必须满足 24 小时真实运行、验签 100%、幂等去重、consumer receipt 可反查、dead-letter replay 有记录且噪声反馈可接受。验收记录使用 [飞书 IM 真实链路 2 小时与 24 小时验收记录模板](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/docs/运维/飞书IM真实链路2小时与24小时验收记录模板.md)。

历史查询的最小 CLI 已补齐：`python -m stability.cli list-runs` 可按 `task_id/status/template_type/package_name/device_id/has_issue/created_from/created_to` 查看 run 摘要，`python -m stability.cli show-run --run-id ...` 可查看单个 run 的实例明细、`report_path`、`html_report_path` 与执行日志路径。

`V2` 的最小分析 CLI 已起步：`python -m stability.cli list-top-issues` 可按 `task_id/status/template_type/version/package_name/device_id/issue_type/created_from/created_to` 聚合并输出 `Top Issue` 列表，`python -m stability.cli show-issue-group --fingerprint ...` 可展开样本事件、报告路径和证据路径，并附带首版规则式 `attribution` 结果。当前 `attribution` 可基于 issue title、summary、process、artifact path、metadata / evidence 等样本信号输出方向、命中规则、命中字段、证据片段、置信度和规则版本，具备最小 evidence-aware 解释；它只是初步归因建议，不是 AI 根因诊断。现在还新增了 `python -m stability.cli compare-issues --dimension version|device|scenario --left-value ... --right-value ...`，用于输出版本、设备、场景三个维度的最小对比结果，包括样本说明、问题变化摘要、不可比提示和样本钻取入口；`python -m stability.cli compare-performance-trends --dimension version|device|scenario --left-value ... --right-value ...`，用于基于已持久化的监控 session 对比 `CPU / memory PSS / FPS / power` 的平均值、峰值、`P95` 和最新值；以及 `python -m stability.cli judge-regression --dimension ... --left-value ... --right-value ...`，用于在现有对比结果上同时给出问题级和指标级回归判断。当前会对 `CPU / memory PSS / FPS / power` 输出 `worsened / unchanged / improved / insufficient_data`，并将指标结论一并纳入整体 `obvious_regression / suspected_regression / no_obvious_change / insufficient_data` 判断。分析快照也已接通：`python -m stability.cli create-analysis-snapshot --snapshot-type top_issues|comparison|regression|replay|review ...` 可把当前分析结果固化到 `runtime/analysis_snapshots/`，其中 `regression` 快照会同时保存 issue 和 metric 两类回归结果，`replay` 快照会同时保存基线/候选规则版本、样本过滤范围、变化摘要，`review` 快照则会在此基础上再保存准入结论、评审发现和审计所需的 `task/run/instance/device/report/log/artifact` 来源引用，不依赖实时重算。当前指纹规则、回归规则和首版归因规则都已外置到本地规则文件，并统一记录 `v1` 规则版本。

第一批规则治理与快照治理能力也已补齐：
- `python -m stability.cli show-analysis-rules`：查看源规则文件、默认规则和当前生效规则
- `python -m stability.cli validate-analysis-rules`：校验规则 JSON 结构、issue type 枚举和值类型
- `python -m stability.cli export-analysis-rules --output ...`：导出生效规则快照，便于留档或回放
- `python -m stability.cli diff-analysis-rules`：比较 `source / effective / default` 三种规则视图，输出字段级差异
- `python -m stability.cli replay-analysis-rules --candidate-path ... [--baseline-path ...]`：用同一批历史 run 数据回放基线/候选规则，比较 `Top Issue` 聚合变化；当前会区分 `regrouped / fingerprint_changed / count_changed / added / removed`
- `python -m stability.cli verify-rule-replay-golden-samples [--suite-path ...] [--case-id ...]`：运行仓库内置的规则回放黄金样本验收集，当前 `v2` 套件已覆盖 `crash / anr / process_exit / startup_timeout / device_offline / reboot` 六类语义，并按 `merge_semantics / identity_semantics / stability_guard` 三层输出结果，用来守住 replay 语义和关键聚合行为
- `python -m stability.cli list-rule-replay-golden-samples [--suite-path ...] [--issue-type ...] [--layer ...] [--expectation ...]`：查看正式 golden suite 的样本清单、分层计数和过滤结果，便于快速确认当前样本库里已经收了哪些 case
- `python -m stability.cli show-rule-replay-golden-sample --case-id ... [--suite-path ...]`：展开一条 golden case 的完整 payload，包括 `dataset / baseline_rules / candidate_rules / expected`
- `python -m stability.cli diff-rule-replay-golden-samples --left-path ... --right-path ... [--case-id ...] [--include-unchanged]`：对比两份 golden suite，输出 `added / removed / modified / unchanged` 差异和字段级 changed_fields，便于回看样本库增删改
- `python -m stability.cli draft-rule-replay-golden-sample --run-id ... --issue-id ... --output ...`：从真实持久化 run 中半自动抽取 issue 事件，生成一条黄金样本草案；会同时写入选中的 task/run/instance/issue 数据、当前基线/候选规则内容，以及一份基于所选样本即时计算出的 replay preview 和 `expected` 草案，方便把真实失败样本沉淀进 golden suite
- `python -m stability.cli promote-rule-replay-golden-draft --source-path ... [--target-path ...] [--case-id ...] [--replace-existing]`：把 draft 文件中的一个或多个黄金样本草案提升进正式 golden suite；提升前会先做结构校验、`case_id` 冲突检查，并对即将写入的 case 再跑一轮 acceptance，只有通过后才真正落盘
- `python -m stability.cli review-analysis-rules --candidate-path ... [--baseline-path ...] [--policy-path ...]`：基于本地准入策略评估一次规则变更，输出 `pass / conditional_pass / fail`、命中发现和样本变化摘要；现在会自动附带一轮 golden suite 结果，把“真实历史样本回放 + 固定黄金样本验收”一起作为准入依据
- `python -m stability.cli create-rule-review-report --name ... [--snapshot-created-by ...] [--decision ...]`：汇总多条 `review` 快照，生成规则评审报告，并同时输出 `JSON / Markdown / HTML`；报告会显式汇总 golden suite 通过情况、样本数和 suite 版本
- `python -m stability.cli compare-rule-review-reports --name ... --left-report-id ... --right-report-id ...`：对比两份规则评审报告，输出摘要 delta、family 差异以及 `JSON / Markdown / HTML` 对比产物；现在 comparison summary 会显式带上左右两侧的 golden suite 汇总和对应 delta
- `python -m stability.cli set-rule-review-report-baseline --baseline-key ... --report-id ...`：把一份已落盘的规则评审报告注册成命名基线
- `python -m stability.cli show-rule-review-report-baseline --baseline-key ...`：查看当前命名基线指向的报告与规则来源
- `python -m stability.cli compare-rule-review-report-against-baseline --name ... --report-id ... [--baseline-key ...]`：把当前评审报告直接对比命名基线；若不传 `--baseline-key`，则会按 `policy_version/candidate_path` 自动选择最近一次无 `fail` 的评审报告作为基线
- `python -m stability.cli promote-rule-review-report-baseline --baseline-key ... --report-id ... [--policy-path ...]`：按基线晋升策略评估当前报告，只有通过后才会真正更新命名基线；CLI 输出会显式带上目标报告和当前基线报告各自的 golden suite 汇总
- `python -m stability.cli list-rule-review-report-baseline-history --baseline-key ...`：查看命名基线的变更历史，包含 `set / rollback` 事件
- `python -m stability.cli rollback-rule-review-report-baseline --baseline-key ... [--target-report-id ...]`：把命名基线回滚到上一个或指定的历史报告版本
- `python -m stability.cli create-rule-review-report-baseline-audit --baseline-key ... --name ...`：把命名基线的完整变更历史固化成一份审计报告，统一输出 `who / when / from / to / why` 时间线和 `JSON / Markdown / HTML` 产物；摘要里会显式包含当前基线报告的 golden suite 汇总
- `python -m stability.cli show-rule-review-report-baseline-audit --baseline-key ... [--limit ...]`：查看某个基线当前 latest 审计摘要、保留策略和最近几版索引，不用手动翻 `index.json`；latest 审计摘要同样会直接带上当前基线报告的 golden suite 汇总
- `python -m stability.cli list-analysis-snapshots / show-analysis-snapshot / delete-analysis-snapshot`
- `python -m stability.cli create-analysis-snapshot --snapshot-type replay --candidate-path ...`：把一次规则回放结果固化成快照，并同时留档基线/候选规则版本、样本范围和来源引用
- `python -m stability.cli create-analysis-snapshot --snapshot-type review --candidate-path ...`：把一次规则准入评审结果固化成快照，并留档策略版本、结论、发现、样本范围和来源引用
- `python -m stability.cli prune-analysis-snapshots --max-count ... --max-age-days ...`：预览或执行快照保留策略；默认只预览，显式 `--execute` 才删除
- Web/文档口径上，规则配置入口当前按“只读规则配置中心 + 候选编辑预览”验收：它可以帮助查看规则来源、默认规则、生效规则，并把候选变更继续引导到校验、diff、回放和评审；它不负责在线保存或发布规则，规则文件仍由本地仓库/本地部署环境管理
- 新创建的分析快照会额外记录 `source_refs`，包含来源 `task/run/instance/device`、报告、执行日志和证据路径；`show-analysis-snapshot` 也会返回 `integrity` 摘要，用于检查这些引用是否仍然存在
- `create-rule-review-report` 生成的评审报告会聚合 `review` 快照的结论分布、规则版本、基线/候选规则来源、变化摘要、高风险 family，以及显式的 golden suite 汇总，并把原始 `review` 快照明细一并留档，便于规则评审和审计复盘
- `compare-rule-review-reports` 会基于已落盘的评审报告输出 `snapshot_count / changed_family_count / finding_count / high_risk_family_count / decision_counts` 的 delta，并给出高风险 family 的 `added / removed / changed / unchanged` 对比结果
- 基线化能力会把“当前候选报告”和“团队已确认基线”解耦：一方面可以显式注册稳定基线键，另一方面也支持按规则版本和候选规则来源自动回退到最近一次可接受报告，减少每次评审都手工挑选 `report_id`
- 基线晋升策略当前由 [config/rule_review_baseline_policy.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/rule_review_baseline_policy.json) 控制，首版规则要求：目标报告的决策类型必须在允许列表内，`changed_family_count_total / finding_count_total / high_risk_family_count` 相对基线不能变差，且 family delta 只允许 `unchanged / removed`；满足这些条件才会真正把基线指向新报告
- 基线历史现在会把每次 `set / promote / rollback` 都记成独立 revision，包含 `revision_id / report_id / changed_at / changed_by / action`，并在可用时附带 `reasons / comparison_id / policy_version` 等审计元数据，因此既可以先做晋升再回滚，也可以后续直接生成完整的基线变更审计报告
- 现在 `set-rule-review-report-baseline / promote-rule-review-report-baseline / rollback-rule-review-report-baseline` 每次成功更新基线后，都会自动刷新该基线的 latest 审计产物，稳定落在 `runtime/analysis_review_report_baseline_audits/latest/<baseline_key>/` 下；同时会维护 `index.json + versions/<revision_id>/` 轻量版本索引，CLI 返回里也会直接带上 latest 路径和当前版本数。首版保留策略默认保留最近 `10` 版 latest，并额外保留 `promote / rollback` 这类关键审计版本

当前分析规则已支持本地文件外置，默认文件是 [config/stability_rules.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/stability_rules.json)。其中当前覆盖三类配置：
- 指纹规则：如 `fingerprint.version`、`ignore_raw_key_issue_types`
- 回归阈值：如 issue/metric 两类阈值与规则版本
- 初步归因规则：如 `attribution.version`、置信度分档、方向规则与关键词命中条件

规则变更准入策略也已外置，默认文件是 [config/rule_review_policy.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/rule_review_policy.json)。当前支持最小策略：
- 全局 change type 阈值：如 `regrouped / fingerprint_changed / added / removed / count_changed` 的 `warning / fail` 门槛
- issue type 专项阈值：如对 `crash / anr / reboot / process_exit` 的更严格 regroup/add/remove 准入限制
- 最低样本覆盖要求：`minimum_family_count`

`judge-regression` 和 `create-analysis-snapshot --snapshot-type regression` 的相关阈值参数现在只会在显式传参时覆盖配置文件默认值；未传参时将直接使用规则文件。

`V1` 验收与回归入口已补齐：`bash scripts/verify_v1_acceptance.sh` 默认执行本地安全基线；若显式追加对应 flag，则可把现有真机 smoke 一并纳入一次性回归。详细清单见 [`Android Stability Lab V1验收清单.md`](../docs/计划/versions/Android%20Stability%20Lab%20V1%E9%AA%8C%E6%94%B6%E6%B8%85%E5%8D%95.md)。另外，`Monkey` 单设备 happy path smoke 脚本已补齐，并已在 `192.168.31.99:5555 / com.hihonor.calculator` 上完成一条真实回归。

CLI 真机 smoke:

```bash
bash -n scripts/verify_v1_acceptance.sh
bash scripts/verify_v1_acceptance.sh
bash -n scripts/verify_extended_artifacts_smoke.sh
scripts/verify_extended_artifacts_smoke.sh --package-name com.example.app --device-id SERIAL --launch-activity .MainActivity
bash -n scripts/verify_cli_query_smoke.sh
scripts/verify_cli_query_smoke.sh --package-name com.example.app --device-id SERIAL --launch-activity .MainActivity
bash -n scripts/verify_monkey_smoke.sh
scripts/verify_monkey_smoke.sh --package-name com.example.app --device-id SERIAL
bash -n scripts/verify_cold_start_loop_smoke.sh
scripts/verify_cold_start_loop_smoke.sh --package-name com.example.app --device-id SERIAL --launch-activity .MainActivity
bash -n scripts/verify_cold_start_loop_multi_device_smoke.sh
scripts/verify_cold_start_loop_multi_device_smoke.sh --package-name com.example.app --device-id SERIAL_A --device-id SERIAL_B --launch-activity .MainActivity
bash -n scripts/verify_cold_start_loop_midrun_disconnect_smoke.sh
scripts/verify_cold_start_loop_midrun_disconnect_smoke.sh --package-name com.example.app --disconnect-device-id SERIAL_A --device-id SERIAL_A --device-id SERIAL_B --launch-activity .MainActivity
bash -n scripts/verify_foreground_background_loop_smoke.sh
scripts/verify_foreground_background_loop_smoke.sh --package-name com.example.app --device-id SERIAL --launch-activity .MainActivity
bash -n scripts/verify_web_tasks_foreground_background_smoke.sh
scripts/verify_web_tasks_foreground_background_smoke.sh --package-name com.example.app --device-id SERIAL
bash -n scripts/verify_install_uninstall_loop_smoke.sh
scripts/verify_install_uninstall_loop_smoke.sh --package-name com.example.app --apk-path /path/app.apk --device-id SERIAL
bash -n scripts/verify_web_tasks_install_uninstall_smoke.sh
scripts/verify_web_tasks_install_uninstall_smoke.sh --package-name com.example.app --apk-path /path/app.apk --device-id SERIAL
bash -n scripts/verify_reboot_loop_smoke.sh
scripts/verify_reboot_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash -n scripts/verify_web_tasks_reboot_loop_smoke.sh
scripts/verify_web_tasks_reboot_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash -n scripts/verify_standby_wake_loop_smoke.sh
scripts/verify_standby_wake_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash -n scripts/verify_web_tasks_standby_wake_smoke.sh
scripts/verify_web_tasks_standby_wake_smoke.sh --package-name com.example.app --device-id SERIAL
bash -n scripts/verify_monkey_midrun_disconnect_smoke.sh
scripts/verify_monkey_midrun_disconnect_smoke.sh --package-name com.example.app --device-id HOST:PORT
bash -n scripts/verify_web_portal_smoke.sh
scripts/verify_web_portal_smoke.sh
```

前置条件:

- `adb` 已在 `PATH` 中可用
- `.venv` 已安装项目依赖，或系统中可用 `python3`
- 目标设备在线，且已安装目标包

成功判定:

- 脚本退出码为 `0`
- 输出中包含 `task_id`、`run_id`、`report_path`
- `report_path` 对应的 `Markdown` 报告文件存在
- `verify_extended_artifacts_smoke.sh` 应稳定触发 `startup_timeout`，并同时落盘 `bugreport.txt`、`dropbox.txt`、`meminfo.txt`
- `verify_cli_query_smoke.sh` 应同时输出 `html_report_path`，并且 `show-device --sync`、`list-devices --sync`、`list-tasks`、`show-task`、过滤后的 `list-runs`、`show-run` 都应真实走通
- `verify_web_portal_smoke.sh` 应成功返回 `/health`、`/`、`/tasks`、`/issues`、`/goldens`、`/goldens/diff`、`/admission`、`/api/home`、`/api/goldens`、`/api/goldens/diff`，并在存在 golden case 时继续下钻 `/goldens/case/<case_id>` 与 `/api/goldens/case/<case_id>`；其中 golden diff 页会使用一份临时 right suite 产物校验 `diff_count`、变更卡片、`change_type` 过滤、`changed_field` 字段级过滤、`case_id` 搜索、左右 case 跳转，以及 `baseline_rules / candidate_rules / filters / expected` 四个关键块的折叠式摘要；在存在基线时继续下钻 `/admission/baseline/<baseline_key>` 与 `/api/admission/baseline/<baseline_key>`，再通过 `/admission/view?path=...` 打开一份评审报告、一份 latest audit 产物，以及可用时的一份 comparison report，在输出目录里保留对应 HTML/JSON 产物
- IM 本地 mock/smoke 单元测试应通过，并能证明 `register-im-webhook`、`run-im-notify-worker`、`im_notify` delivery channel、`asl.im_notify.v1` body、delivery/consumer receipt 和 worker status 的平台侧路径可用；如果本地 mock endpoint 没有 pending event，只能判定注册和空队列 worker 正常，不能判定投递成功
- `Monkey` 单设备 smoke 应输出 `run_status=success` 且实例 `success`
- 多设备 smoke 会输出 `instance_status_counts` 与 `report_paths`，且实例数应与传入设备数一致
- 中途掉线 smoke 会输出 `run_status=success`，断开目标实例应可在每轮开始前或启动命令失败后自动重连并最终为 `success`
- `foreground_background_loop` 单设备 smoke 会通过 CLI 创建任务、创建 Run 并执行一轮前后台切换，输出 `run_status=success`、唯一实例 `success` 和有效 `report_path`
- `/tasks` Web 单设备 smoke 会启动本地 Web，先访问 `/tasks` 确认页面表单，再通过 HTML action 提交创建任务、创建 Run 和执行 Run，最后用 `/api/runs/<run_id>` 校验 `run_status=success`、唯一实例 `success` 和有效 `report_path`
- `install_uninstall_loop` CLI/Web smoke 会要求 `--apk-path`，默认先 `adb install -r` 做覆盖安装预置，再执行安装卸载循环；它会改变目标 App 安装状态，务必使用可安全重装的测试包
- `reboot_loop` CLI/Web smoke 会真实执行 `adb reboot`，只应在可安全重启的设备上显式运行
- `standby_wake_loop` CLI/Web smoke 会真实发送息屏/唤醒按键事件，可能受锁屏和厂商电源策略影响
- `Monkey` 中途掉线 smoke 会输出 `run_status=success`，并且 `execution.log` 中应包含 `reconnect recovered command path`

失败判定:

- 脚本退出码非 `0`
- 输出中仍会打印 `output_dir`，其中保留 `create_task.json`、`create_run.json`、`execute_run.json` 及各自 `stderr`
- 若为启动超时，报告中应包含 `Startup Summary` 与 `startup_timeout` issue
- 若为多设备并发失败且传入 `--stop-on-failure`，未开始实例应被标记为 `cancelled`
- TCP 设备当前仅支持自动重连一次；该策略已通过共享 helper 接入 `cold_start_loop` 与 `Monkey`，其中 `cold_start_loop` 覆盖每轮开始前以及启动命令失败/超时后的当前轮重试，`Monkey` 覆盖启动前离线以及命令失败/超时后的当前执行重试，若这次重连仍失败，执行会落为失败
- IM 本地 mock/smoke 失败只说明平台侧出站合同、worker、receipt 或本地接收器有问题；即使本地 smoke 成功，也不能据此标记真实 IM 链路完成，仍需真实 endpoint 完成 2 小时试运行和连续 24 小时验收

# Android Stability Lab V3 开发计划

## 1. 文档定位

本文档基于主文档《Android Stability Lab开发计划》第 6 章 `V3` 开发计划展开，目标是在不突破主文档版本边界的前提下，将 `V3` 从阶段性方向补充为可执行、可跟踪、可验收的版本计划。

本文档聚焦以下建设主题：

- 无人值守能力
- 质量门禁能力
- 团队协作流转
- 外部系统集成
- Web 主入口建设

本文档默认以前序版本能力为基础：

- `V1` 已具备稳定的任务执行、异常检测、证据抓取和报告能力
- `V2` 已具备可信的问题聚合、对比分析、回归判断和分析快照能力

### 1.1 状态维护规则

- `V3` 任一阶段有实际开发落地后，必须在同一轮同步更新本文件对应阶段的标题状态短句和“当前开发状态”
- 更新时不能只改阶段正文，不改标题；也不能只改总计划摘要，不改本子计划
- 阶段标题应明确写出“当前状态 + 已落地内容 + 主要剩余缺口”，保证只看标题也能判断推进程度

### 1.2 本轮文档验收定位

本轮同步的重点是把 `V3` 阶段 1 的长稳能力收敛为“本地长稳产品化最小闭环”：用户可以在本地部署中按包名、任务名、长稳模板、运行策略、设备策略和监控策略创建长稳任务，并能在真实设备上至少完成一轮执行，随后把执行结果串到 `/tasks`、`/runner`、`/performance` 以及日报/周报。

本轮不把能力描述为团队级设备预约或排班平台。当前设备治理只按本地无人值守调度辅助验收，包括主备设备、轮转、候补/空闲池补位、隔离和恢复探测；团队预约、借用审批、团队配额、维护窗口、冲突处理、按团队隔离可见性和排班日历仍是后续缺口。

## 2. V3 版本目标

`V3` 的目标不是继续扩充单点测试能力，而是将现有执行与分析能力升级为可进入团队日常生产流程的协作平台，使平台能够承接持续运行、质量判断、多人协同和外部联动。

`V3` 完成后应具备以下结果：

- 平台能够支持较长时间持续运行，并具备基础自恢复与隔离能力
- 测试结果能够形成可审计的门禁结论，而不只是分析展示
- 团队成员能够围绕问题和门禁结果进行协作处理
- 平台能够对接提测、通知、缺陷和持续集成链路
- Web 页面成为团队统一主入口，而不是依赖本地工具拼装使用

## 3. 版本边界

### 3.1 包含范围

- 围绕 `7x24` 运行所需的轮转、补位、恢复、隔离和可观测能力
- 围绕质量门禁所需的规则配置、结论生成、人工确认和审计留痕
- 围绕团队协作所需的角色、认领、评论、状态流转和结论沉淀
- 围绕生产链路所需的提测平台、IM、缺陷系统、`CI/CD` 对接
- 围绕统一使用入口所需的 Web 首页、任务大厅、问题中心和准入中心

### 3.2 不在本版本重点扩展的范围

- 不在 `V3` 内重做 `V1` 的执行底层架构
- 不在 `V3` 内重新定义 `V2` 的问题指纹和分析方法体系
- 不将 `V3` 扩展为复杂的项目管理系统或完整缺陷系统替代品
- 不在本版本默认覆盖大量定制化审批链路

### 3.3 建设前提

- `V1` 的任务执行与证据链路已达到可长期运行的稳定度
- `V2` 的聚合与回归结论具备较高可信度
- 设备、任务、问题、快照、报告等核心对象已有统一标识和可追踪关系

## 4. 阶段拆分总览

| 阶段 | 阶段目标 | 交付重点 |
| --- | --- | --- |
| 阶段 1 | 建立无人值守运行底座 | 长稳轮转、最小长稳模板族画像/配置建议、自动补位、自动恢复、隔离策略、运行可观测 |
| 阶段 2 | 建立质量门禁闭环 | 门禁规则、门禁结论、人工确认、审计记录、基线辅助判断 |
| 阶段 3 | 建立团队协作闭环 | 角色模型、认领机制、评论讨论、状态流转、协作留痕 |
| 阶段 4 | 建立外部联动闭环 | 提测平台、IM、缺陷系统、`CI/CD` 对接 |
| 阶段 5 | 建立 Web 主入口 | Web 首页、任务大厅、问题中心、准入中心 |

建议采用“先后台能力、后统一入口；先核心闭环、后外围扩展”的推进方式，避免先搭壳子再补核心逻辑。

## 5. 分阶段开发计划

## 5.1 阶段 1：无人值守能力（已完成一部分，已落地本地长稳产品化最小闭环的后台基础、单实例锁与运行心跳、最小定时 patrol runner、主备设备/轮转/候补与空闲池补位、隔离后自动恢复探测、基础巡检摘要、自动日报/最小周报生成、Web 巡检状态页、首页摘要卡和最小长稳模板族画像/配置建议，剩更清晰长稳配置入口、真实长稳专项样本、通知、更正式后台部署；团队级设备预约/配额/排班不属于本轮完成能力）

### 5.1.1 阶段目标

让平台具备较长周期连续运行能力，使任务能够在设备异常、执行失败、资源波动等情况下自动处理常见问题，减少人工值守成本。

当前开发状态：

- 已落地执行级稳定性底座：`execute-run` 受控并发、`stop_on_failure`、按失败类型分类重试、失败后清理、TCP 设备单次重连恢复
- 已落地场景级恢复：`cold_start_loop` 与 `Monkey` 已覆盖启动前和部分命令失败窗口的 TCP 自动恢复
- 已落地首批模板扩展：任务模板已从 `monkey / cold_start_loop / custom` 扩到 `foreground_background_loop / install_uninstall_loop / reboot_loop / standby_wake_loop`
- 已具备最小长稳模板族画像和配置建议：当前可把 `monkey / cold_start_loop / foreground_background_loop / install_uninstall_loop / reboot_loop / standby_wake_loop / custom` 按长稳目标组合进无人值守任务，并复用轮转、补位、隔离恢复、巡检摘要和日报/周报链路；这属于模板化建议和运行画像，不等于完整独立长稳产品
- 本轮验收应按本地长稳产品化最小闭环表述：用户能够围绕包名、任务名、长稳模板、运行策略、设备策略和监控策略创建无人值守长稳任务，并在本地 Web/API/CLI 主链里看到任务、轮次、设备、巡检和报告的关联；这不是团队级设备预约、借用审批、配额或排班平台
- 已落地基础运行可视化入口：Web 首页、任务大厅和准入中心已能展示设备摘要、最近 Run、失败情况和基线 latest 审计摘要
- 已落地最小无人值守后台闭环：`configure-unattended-task / list-unattended-tasks / show-unattended-task / run-unattended-round / patrol-unattended-tasks`
- 已落地周期触发与轮次记录：无人值守任务可保存 `interval_minutes / next_run_at / last_run_at / recent_rounds / latest_summary`，并通过 `patrol-unattended-tasks` 按到期时间批量触发
- 已落地更完整长稳轮转：`configure-unattended-task` 已支持 `fixed / round_robin` 两种主设备轮转策略，以及 `every_round / failure_only` 两种轮转推进策略；当前会持久化 `rotation_cursor / rotation_advance_count / recent_device_windows / long_run_summary`
- 已落地候补设备补位：当主设备不可调度时，会从候补池或当前空闲设备池里自动补位，并把替换关系写入轮次记录
- 已落地设备隔离：设备连续失败达到阈值后会自动置为 `quarantined`，并进入巡检摘要统计
- 已落地隔离后自动恢复探测：`patrol-unattended-tasks` 会对 `quarantined` 设备做节流探测，设备重新上线后会自动解除隔离，并把探测/恢复结果写入巡检摘要
- 当前设备池治理边界应限定为本地无人值守调度辅助：可记录主设备、备设备、目标设备数、轮转策略、补位事件、不可调度设备和隔离恢复结果；尚未提供团队预约、设备借用审批、团队配额、维护窗口、冲突处理或按团队隔离可见性的设备池平台
- 已落地最小定时 patrol runner：`run-unattended-patrol-runner` 可按秒级间隔循环调用 patrol，并输出每轮巡检摘要和最终停止原因，便于先挂到系统调度或 supervisor
- 已落地单实例锁与运行心跳：runner 会在 `runtime/unattended_runner/` 下维护 `runner.lock` 和 `runner_status.json`，用于拒绝重复实例、保留最新运行状态，并在 stale lock 场景下自动接管
- 已落地长稳日报：`build-unattended-daily-report` 可基于已保留的无人值守轮次历史生成日级汇总；runner 也会在每轮 patrol 后自动刷新 `runtime/unattended_runner/daily_reports/<YYYY-MM-DD>/report.json + summary.md`
- 已落地最小周报：`build-unattended-weekly-report` 可基于已保留的无人值守轮次历史生成周级汇总；runner 也会在每轮 patrol 后自动刷新 `runtime/unattended_runner/weekly_reports/<YYYY-Www>/report.json + summary.md`
- 已落地最小后台巡检摘要：当前会输出失败率、掉线率、恢复成功率、隔离设备数，以及隔离探测次数、跳过次数、恢复设备数和每个无人值守任务的最近运行摘要
- 已落地 Web 巡检状态页：`/runner` 和 `/api/runner` 会直接展示 patrol runner 的锁状态、心跳、latest daily report / latest weekly report 摘要、最近一轮巡检摘要和路径信息，方便先做值班视角排查
- 已落地最近 patrol 历史列表：runner 心跳文件现在会保留有限长度的 `recent_patrols`，`/runner` 和 `/api/runner` 可直接回看最近几轮 patrol 的执行/失败/掉线/恢复/隔离摘要
- 已落地失败轮次快速过滤：`/runner` 和 `/api/runner` 已支持按 `全部 / 失败轮次 / 掉线轮次 / 隔离轮次` 快速筛选最近 patrol 历史，便于值班时直接聚焦异常轮次
- 已落地异常轮次详情展开：`/runner` 页面里的异常 patrol 轮次现在支持直接展开查看 `task_count / due_task_count / skipped_task_count / probe_attempts / probe_recovered` 等摘要，不必先回原始 JSON
- 已落地异常轮次一键跳转：`/runner` 页顶部现提供 `一键看失败轮次 / 掉线轮次 / 隔离轮次` 快捷入口，可直接跳到对应过滤结果
- 已落地最新心跳关联提示：`/runner` 页顶部现在会直接判断“最新心跳对应的最新 patrol 是否异常”，并在异常时给出跳到失败/掉线/隔离过滤结果的快捷入口
- 已落地任务影响范围提示：`/runner` 页顶部的最新心跳关联提示现在会同时给出 `task_count / due_task_count / executed_task_count / skipped_task_count`，方便先判断异常是局部抖动还是已经影响整轮巡检
- 已落地异常严重度分层：`/runner` 页现在会按 `正常 / 中 / 高 / 严重` 给最新 patrol 和最近 patrol 历史做分层，其中掉线波动记为 `中`，出现失败记为 `高`，出现隔离设备或“失败伴随任务跳过”记为 `严重`
- 已落地严重度过滤：`/runner` 和 `/api/runner` 已支持 `severity_filter=medium|high|critical`，并且可以和现有 `patrol_filter` 叠加使用，便于先只看高优先级异常轮次
- 已落地首页巡检摘要卡：Web 首页会直接展示 runner 的状态、锁状态、heartbeat age、cycle 数、latest daily report / latest weekly report 摘要和最近一轮巡检的执行/隔离摘要，并把 `latest daily report` 的失败轮次、隔离设备和失败/掉线率一并纳入异常态判断，对 `stale / missing / failed` 以及“日报已异常”这类状态做高亮提示、操作建议和可直接点击的动作入口
- 尚未落地完整独立长稳模板产品化能力；仍需补更明确的模板入口、推荐参数沉淀、专项长稳验证样本、配置校验和更正式产品化配置面
- 尚未落地通知订阅和长期后台部署/守护方案
- 尚未落地团队级设备调度治理；如后续要服务多个团队，应补设备预约/借用、团队配额、维护窗口、冲突处理、责任人视图和通知联动，同时继续保留本地部署与导出共享口径

### 5.1.2 重点任务拆分

#### 模块 A：长稳轮转

- 定义长周期任务运行模型，包括轮次、时段、设备占用和任务窗口
- 支持定时触发、周期触发和队列触发
- 建立任务续跑、补跑和轮次汇总规则

#### 模块 B：自动补位

- 在设备不可用、任务失败或资源不足时自动选择候补设备
- 明确补位适用范围、补位次数和回退策略
- 区分“执行失败补位”和“设备异常替换”两类场景

#### 模块 C：自动恢复与隔离

- 对常见故障建立自动恢复动作，例如重连、重试、重启代理、重置任务
- 对反复失败设备建立隔离策略，避免拖垮整体任务池
- 建立恢复失败后的人工介入入口和告警机制

#### 模块 D：运行可观测

- 建立任务运行态、设备运行态和系统健康态视图
- 建立队列积压、失败率、掉线率、恢复成功率等指标
- 建立关键异常事件日志和巡检面板

### 5.1.3 交付物定义

- 无人值守任务调度与轮转机制
- 最小长稳模板族画像与配置建议
- 候补设备与自动补位策略
- 自动恢复动作集合与隔离策略
- 运行态监控指标与后台巡检页
- 长时间运行专项验证记录

### 5.1.4 依赖关系

- 依赖 `V1` 的任务调度、执行状态、失败重试和设备状态能力
- 依赖 `V2` 的任务结果归档和问题判定结果，用于长周期统计
- 依赖统一日志、告警和存储能力支撑运行追踪

### 5.1.5 验收标准

- 用户可以按包名、任务名、长稳模板、运行策略、设备策略和监控策略创建本地长稳任务；运行策略至少能表达周期/轮次触发，设备策略至少能表达主设备、候补设备或空闲池补位，监控策略至少能进入巡检摘要、异常过滤和日报/周报口径
- 至少使用一台真实设备完成一轮长稳任务执行，并能追踪到任务配置、Run/轮次记录、设备选择或补位结果、执行状态、失败摘要和产物路径
- 结果链路必须能串到 `/tasks`、`/runner`、`/performance` 以及长稳日报/周报；其中 `/tasks` 看任务与 Run，`/runner` 看 patrol/心跳/异常轮次，`/performance` 看性能趋势或风险摘要，日报/周报看跨轮汇总
- 设备断连、任务失败、重试、隔离和恢复探测必须有记录，可在轮次记录、巡检摘要、runner 历史或日报/周报中复核，不能只依赖临时控制台输出
- 平台可连续运行预设长稳周期，期间核心任务链路不中断
- 常见设备掉线或执行失败后可自动恢复或自动补位
- 同一故障不会导致队列长期阻塞
- 巡检页可明确展示失败、恢复、隔离和积压情况
- 当前验收不覆盖团队级设备预约、借用审批、团队配额、维护窗口、冲突处理、按团队隔离可见性或排班日历

### 5.1.6 主要风险

- `adb` 或设备连接不稳定导致恢复策略效果不稳定
- 长周期运行产生状态脏数据和资源泄漏
- 自动恢复动作过于激进，可能掩盖真实异常

## 5.2 阶段 2：质量门禁（已完成一部分，已落地规则治理、回放、评审、基线审计、结构化准入 report payload/API/页面摘要、本地规则治理最小闭环，剩 Git/PR 式规则发布流、Web 写操作身份绑定、更正式门禁对象和完整对外报告/审批流）

### 5.2.1 阶段目标

让平台能够基于执行与分析结果给出可使用的准入判断，并支持人工确认、留痕和追溯，形成从“发现问题”到“给出结论”的流程闭环。

当前开发状态：

- 已落地规则治理主链：`show/validate/export/diff/replay/review-analysis-rules`
- 已落地黄金样本验收与准入整合：`golden suite` 已作为 `review-analysis-rules` 的自动准入依据之一
- 已落地评审报告、报告对比、命名基线、基线晋升、历史回滚和 latest 审计自动刷新
- 已落地 Web 准入中心与基线详情，可直接查看 `review / comparison / latest audit / golden suite` 状态、历史时间线与审计产物
- 已落地结构化版本测试报告 / 准入报告阶段形态：通过 `AdmissionCase`、`/api/admission`、`/api/admission/cases`、准入中心和基线详情页展示 report payload、质量门禁摘要、证据链、source refs、latest audit、comparison report 和最近版本索引
- 已落地更正式规则配置入口的阶段形态：可查看当前规则来源、默认规则、生效规则，并对候选规则做编辑预览、校验、diff、保存候选、审批/拒绝、发布版本记录、回滚和本地 actor 权限绑定；Web/API 可暴露治理台账摘要
- 当前共享口径仍是本地部署页面、报告/JSON/HTML/Markdown 导出和审计/对比产物跳转，不是完整对外 PDF、邮件自动分发或多级签核审批流
- 尚未落地 Git/PR 式规则发布流、Web 写操作身份绑定、更正式的门禁规则对象治理和完整对外报告发布流

### 5.2.2 重点任务拆分

#### 模块 A：准入规则管理

- 当前阶段已具备本地规则治理最小闭环，用于查看规则来源、默认规则、生效规则、预览候选变更影响、保存候选、审批/拒绝、发布版本记录、回滚和本地 actor 权限绑定
- 规则变更仍以本地规则文件为主，配合导出快照、回放、准入评审和评审报告完成治理；当前 CLI 可执行写操作，Web/API 先暴露治理台账摘要，不按完整 Web 规则发布后台验收
- 后续再定义更完整门禁规则对象，包括规则范围、目标对象、阈值、触发条件和优先级
- 后续支持按应用、版本、场景、设备组等维度配置规则
- 后续区分阻塞型规则、提醒型规则和人工确认型规则，并接入审批、发布、回滚和权限约束

#### 模块 B：准入结论生成

- 根据 `V2` 聚合、回归和趋势结果生成准入结论
- 支持通过、警告、阻塞、待确认等结论状态
- 保留结论生成依据，能够追溯到问题、报告、快照和对比结果

#### 模块 C：人工确认与审计

- 支持对自动门禁结论进行人工确认、驳回、放行和备注
- 建立结论操作日志和审计记录
- 明确谁在何时基于什么依据做了何种变更

#### 模块 D：性能基线辅助判断

- 将关键性能指标趋势纳入辅助判断
- 识别无崩溃但存在明显性能退化的场景
- 区分“辅助提示”与“强阻塞依据”，避免误伤

### 5.2.3 交付物定义

- 门禁规则模型与规则配置入口；当前阶段按本地规则治理最小闭环验收，不按 Git/PR 式发布平台或完整 Web 在线规则编辑器验收
- 门禁结论计算服务与结构化准入 report payload/API；当前不按完整 PDF/邮件/审批流验收
- 人工确认流和审计记录能力
- 准入结果展示页和结论详情页
- 门禁回放与验证样例集

### 5.2.4 依赖关系

- 强依赖 `V2` 的问题指纹、聚合、回归和趋势分析可信度
- 依赖统一身份体系，用于确认操作人和审计记录
- 依赖规则配置存储和历史结论归档能力；当前规则源仍以本地文件管理为主，导出规则快照、评审报告、JSON/HTML/Markdown 产物仍是共享主口径

### 5.2.5 验收标准

- 典型发版或提测场景中，可自动生成准入结论
- 门禁结论能够清晰展示触发依据和关联问题
- 版本测试报告 / 准入报告可通过 Web/API 查看结构化摘要、证据链、审计/对比产物和最近版本索引；共享时优先导出报告、JSON/HTML/Markdown 和运行产物
- 规则配置入口能够展示当前规则、预览候选变更影响，并通过 CLI 完成候选保存、审批/拒绝、发布版本记录、回滚和权限绑定；但不会误导用户以为已经具备 Git/PR 式发布平台或完整 Web 在线规则编辑器
- 不将当前 report payload/API/页面摘要误验收为完整对外 PDF、邮件自动分发或正式多级审批流
- 人工放行和驳回操作具备完整留痕
- 性能辅助判断不会无依据地直接替代核心质量结论

### 5.2.6 主要风险

- `V2` 误判会直接传递为门禁误判
- 规则粒度不足会导致误伤或漏判
- 如果把本地规则治理最小闭环误写成完整在线规则发布平台，后续验收会错误期待 Git PR/代码评审式发布、Web 写操作后台、组织级权限继承和跨团队审批流
- 人工确认权限与责任边界不清，影响流程可信度

## 5.3 阶段 3：协作流转（已启动最小可写闭环，当前已具备 Issue + AdmissionCase 的本地认领/评论/状态流转与留痕，并部分落地受信 header SSO 写操作边界、最小用户目录和只读责任检索，仍缺完整 IAM、自动责任同步和更复杂权限治理）

### 5.3.1 阶段目标

让团队成员能够围绕问题和门禁结果进行分工、认领、讨论和结论沉淀，避免平台停留在“只出结果、无人处理”的状态。

当前开发状态：

- 已具备协作前置条件：问题、报告、快照、基线、审计产物已有统一标识和只读查看入口
- 已具备基础留痕：规则评审、基线变更、回滚和审计报告都能记录 `who / when / from / to / why`
- 已落地最小协作对象：角色、操作人、问题协作记录、`AdmissionCase` 协作记录、评论和事件留痕
- 已落地最小可写动作：问题与 `AdmissionCase` 的认领、评论、状态流转，并可在 Web 和本地存储中追溯
- 已落地最小协作视图：`待我处理 / 待确认准入 / 已放行但有风险`
- 已落地正式化中的本地身份边界：写操作只接受服务端解析身份，已支持本地 session 签发、过期、吊销和 token 生命周期治理，审计中稳定记录 `identity_id / session_id / auth_mechanism / session_source / audit_event_id / permission_check_id`
- 已部分落地正式在线身份边界的最小接入形态：服务层新增外部身份绑定，`CollaborationSession` 可记录 provider、external subject 和 organization，`resolve_sso_actor` 可解析受信 SSO claims、稳定绑定外部身份、校验组织边界、签发 SSO session 并增强审计字段
- 已部分落地统一用户目录的最小只读/审计形态：新增 `CollaborationUserProfile`，可聚合 actor、外部身份、email、display name、organization、teams、role、permissions 和 last_seen；`resolve_sso_actor` 会同步目录 profile，同一 external subject 重复解析时 profile id 保持稳定，并更新 display/team/role/last_seen
- 已部分落地跨系统责任检索的最小只读形态：服务层 profile 可被 Web/API 复用，平台可从 actor/profile、外部身份、issue assignee、`AdmissionCase` assignee/final_reviewer、defect team_key、release owner_team 汇总责任线索
- 当前这层边界仍保留本地部署场景：默认不是“不同人看不同数据”的在线平台，本地 session / actor 路径仍可用；身份主要用于写操作校验、事件回放、责任追踪和审计检索
- 尚未落地完整 OIDC/LDAP/SSO 产品、独立 IAM/团队管理存储、真正跨系统责任自动同步、批量操作和更复杂的多级权限治理

### 5.3.2 重点任务拆分

#### 模块 A：本地会话、受信 SSO claims 与写操作边界

- 建立本地 session 的签发、过期、吊销和校验能力
- 支持从可信 Web/API 边界传入的 SSO claims 解析和外部身份绑定
- 对受信 claims 中的 organization 做最小组织边界校验
- 控制关键操作权限，包括规则编辑、放行、关闭问题等
- 统一写操作审计事件编号，便于回放、追责和外部链路消费

当前说明：

- 当前实现已经有本地 actor 注册表、`identity_id`、可签发 session、`session_id`、`auth_mechanism`、`audit_event_id` 和 `permission_check_id`
- 当前实现已新增 `CollaborationExternalIdentity`，并在 session 中补充 provider、external subject、organization 等字段
- 当前实现已新增 `CollaborationUserProfile`，并提供 `list_user_profiles / get_user_profile / sync_user_profile_from_sso`，用于从本地 actor 与外部身份派生最小用户目录
- 受信 SSO claims 已能进入服务层解析链路，审计可补充 `identity_provider / external_subject_id / external_email / organization_id / team_ids`
- 这层能力的目标是先把“服务端解析身份”“受信 header SSO 最小接入”“写操作 permission check”“审计字段稳定化”和“目录 profile 稳定派生”做起来，避免 Web 继续信任表单里的 `actor_id`
- 这不是完整企业级 SSO；它更适合在可信反向代理/网关注入并清洗 header 后，作为正式在线身份边界的最小接入形态。后续若真要走完整团队在线平台，再补 OIDC/LDAP/SSO、统一用户源、租户/组织边界和更细权限继承模型

#### 模块 B：问题认领与处理流转

- 支持问题认领、转派、处理中、已确认、已解决、已忽略等状态
- 支持按问题聚合对象或具体实例进行处理
- 支持与门禁结论联动展示当前处理状态

当前说明：

- 问题侧最小流转已落地：`assign / comment / transition`
- `AdmissionCase` 侧最小流转已落地：`assign / comment / transition`
- 当前 AdmissionCase 状态集以 `new / assigned / reviewing / pending_confirmation / approved_with_risk / approved / rejected` 为最小闭环
- `AdmissionCase` 的 `status / assignee / final_reviewer` 会同步回持久化 case 对象，因此 CLI、Web、API 看到的是同一条准入单状态，而不是散落在协作事件里的派生值

#### 模块 C：评论与结论沉淀

- 支持问题和门禁结果下的评论讨论
- 支持记录处理结论、复现结论和风险说明
- 支持沉淀处理备注，避免重复排查

当前说明：

- 问题和 `AdmissionCase` 都已经支持评论
- `AdmissionCase` 详情页现在会展示协作时间线，可回看 `action / created_by / session_source / audit_source`
- 这层时间线的目标是先沉淀“谁在什么时候基于什么身份做了什么”，为后续接 IM/缺陷系统和完整企业级 SSO 留审计基础

#### 模块 D：协作可视化

- 支持查看待处理问题、待确认门禁、我的认领项
- 支持按状态、责任人、应用、版本筛选
- 支持查看处理时效和协作积压情况

当前说明：

- 准入中心已提供三个最小协作视图：`待我处理 / 待确认准入 / 已放行但有风险`
- Web/API 已提供 `/api/users` 与 `/api/responsibility` 只读入口，可用于用户目录查看、责任线索检索和审计增强
- 当前视图仍是本地运维控制台级别，适合值班和排查，不等于正式团队待办中心
- 后续如需团队化使用，仍需补更明确的筛选、时效统计、批量操作和通知联动

### 5.3.3 交付物定义

- 基础角色与权限模型
- 最小只读用户目录和责任检索 API
- 问题流转状态机
- 评论与操作留痕能力
- 协作视图，例如待办列表、我的任务列表
- 协作流程使用规范

### 5.3.4 依赖关系

- 当前最小闭环不再阻塞于完整企业级 SSO；已先用本地 actor 注册表、本地签发 session、受信 SSO claims 和派生 user profile 把服务端身份解析、permission check、组织边界最小校验、审计边界与只读责任检索做出来
- 后续若进入完整团队在线平台阶段，再补统一身份认证、用户体系、组织/租户模型和更细权限继承
- 依赖问题中心、门禁中心的对象统一建模
- 依赖消息通知能力支撑认领和状态变更提醒

### 5.3.5 验收标准

- 问题可完成认领、转派、关闭等基本协作流转
- 门禁结论可关联责任人与处理说明
- 评论和关键操作均可追溯到操作人和时间
- 本地值班和排查时，使用者可以直接看到统一数据；需要共享时更推荐导出报告、JSON 或产物给别人看

当前阶段补充验收口径：

- `AdmissionCase` 可完成认领、评论、状态流转，并把状态同步回 case 对象
- Web 写操作不会直接信任表单身份字段，必须由服务端解析出有效本地 session、本地 actor 或受信 SSO claims
- SSO header 不完整时写操作应拒绝而不是静默回退；完全没有 SSO header 时，本地 session / actor 兼容路径仍可使用
- 协作审计中可稳定回看 `identity_id / session_id / auth_mechanism / session_source / audit_event_id / permission_check_id`，受信 SSO 路径还应包含 provider、external subject、external email、organization、team 和 request id
- 用户目录可通过本地 actor 与外部身份派生 profile，并支持按 profile id 查询；重复 SSO 解析同一 external subject 时 profile id 应保持稳定
- 责任检索可只读汇总 issue、AdmissionCase、defect、release submission 等对象上的责任线索，但不改变责任写入或外部系统同步业务流
- 受信 SSO claims 只作为写操作身份边界和审计增强，不改变“查看者默认看到同一份平台数据”的当前产品形态
- 准入中心至少能直接回答三个问题：什么需要我处理、什么还待最终确认、什么虽然已放行但仍有风险

### 5.3.6 主要风险

- 流转状态过多，导致使用复杂度上升
- 权限模型设计过重，拉高上线门槛
- 受信 SSO header 必须由可信反向代理或网关注入并清洗外部同名 header；portal 只消费 trusted header，不负责防伪源头
- `trusted_organization_ids` 未配置时只能要求 claims 内存在 organization，不能限制具体组织
- 用户目录基于现有本地 actor 与 `identities.json` 派生，没有独立 IAM/团队管理存储；role/permissions 可用于审计展示，但权限行为仍走现有 permission matrix
- 责任检索当前只是只读聚合，字段采用宽容读取，不代表跨系统责任已自动同步或 schema 已完全收紧
- 协作动作与缺陷系统职责重叠，造成双写负担

## 5.4 阶段 4：外部系统集成（已完成 CI + IM + 缺陷系统 + 提测平台四条平台侧正式入口和本地 outbox 运维面，IM/飞书真实链路仍需按“本地 smoke -> 真实 2 小时试运行 -> 真实 24 小时”完成验收）

### 5.4.1 阶段目标

让平台能够进入团队已有发布与协作链路，减少人工搬运结果和重复录入动作，提升平台的接入价值。

当前开发状态：

- 已具备可被对接的本地能力：CLI、Web、报告、快照、基线审计、规则评审报告和 JSON 产物路径都已成型
- 已落地最小 outbox 事件出口，可沉淀问题认领、评论、状态流转、人工覆盖等事件
- 已具备本地 webhook 注册与单链路投递能力，可通过 CLI 把 pending 事件推送到一条实际 callback/webhook 链路
- 已补最小 outbox 运维面：`run-integration-outbox-worker` 可按 webhook 跑多轮 delivery worker，`replay-integration-dead-letters --execute` 可把 dead-letter 事件重新排回 pending；`/api/integration/outbox` 同步 worker_status、delivery_receipt、consumer_receipt 与幂等 key（含 replay/retry 观测）
- 当前阶段已打通最小外部闭环：`sync-ci-admission-decisions`，可查询 pending admission 决策并回传到 CI（支持单次查询+可选自动建链+投递）
- 已落地 IM/飞书平台侧正式入口：`register-im-webhook` / `run-im-notify-worker`、`register-feishu-webhook` / `run-feishu-notify-worker`、Web 集成页 IM 注册与 worker 入口，以及 `im_notify` / `feishu_bot` delivery channel；消息体现在会按 `asl.im_notify.v1` 或飞书机器人格式把协作事件、准入结论与 outbox 告警整理成稳定通知合同。该状态表示平台侧入口、合同和本地 worker 面已具备，不表示真实 IM endpoint 已完成 2 小时试运行或 24 小时联调
- 已落地缺陷系统最小正式链路：问题侧已支持创建缺陷请求、回填外部缺陷链接、同步外部状态，并会把 `issue.defect_create_requested / issue.defect_linked / issue.defect_status_synced` 通过 `defect_sync` delivery channel、Webhook、Worker 和 `asl.defect_sync.v1` 合同统一投递；问题关闭前也会校验至少存在一个达到可关闭状态的关联缺陷
- 已落地提测平台最小正式链路：`ReleaseSubmissionService` 可接收提测上下文、创建稳定性任务与 Run、可选立即执行，并把执行状态和 `AdmissionCase` 准入结果同步到同一个 `ReleaseSubmissionRecord`；CLI/Web/API 已提供创建提测请求、同步提测准入、注册提测 Webhook 和运行提测同步 worker 的入口，出站消息使用 `release_submission` delivery channel 和 `asl.release_submission.v1` 合同
- 当前事件已具备 `delivery_status / attempt_count / last_error / next_retry_at / signature / retry_backoff_seconds / dead_lettered_at / alert_status` 等最小投递状态，可回看是否真正出站
- `/api/integration/outbox` 已同步暴露 worker 配置、worker_status、delivery/consumer 收据、幂等 key 与 delivery/replay 关键状态，Web/CLI 运维口径已开始统一
- P0 真实链路运营建议先选择 IM/飞书通知链路，按 `docs/运维/IM通知真实链路长时联调Runbook.md` 执行“三段式验收”：先用本地 mock/smoke 验证 webhook 注册、worker 启动、`asl.im_notify.v1` payload、签名 header、receipt、dead-letter replay 和运维观测面；再用真实飞书 endpoint 跑满 2 小时试运行，验证 `FEISHU_WEBHOOK_URL / FEISHU_SIGNING_SECRET`、worker、签名、receipt、限流和噪声；最后跑满真实 24 小时，验证签名/幂等/receipt、失败分级、dead-letter replay、订阅/噪声治理、暂停/回滚和长时稳定性。CI 链路保留为第二条真实平台适配对象
- 目前仍以本地使用为主，更复杂多链路并发、真实外部平台适配、订阅治理和长时 worker 联调仍待后续阶段；其中“长时 worker 联调”应优先按一条 IM/飞书链路完成本地 smoke，再完成真实 2 小时试运行，最后跑通真实 24 小时。不能把本地 smoke 或 2 小时试运行写成真实链路已完成
- 正式在线鉴权、组织级授权、多目标补偿策略和复杂回写协议仍待后续建设

### 5.4.2 重点任务拆分

#### 模块 A：提测平台集成

- 接收提测请求或提测上下文
- 关联测试对象、版本信息和执行计划
- 将门禁结果回写或反馈给提测流程

#### 模块 B：IM 通知集成

- 支持任务异常、门禁结果、认领变更等通知
- 支持按应用、版本、责任组配置订阅
- 控制通知噪声，避免重复轰炸

#### 模块 C：缺陷系统集成

- 支持从聚合问题或门禁阻塞结果创建缺陷
- 支持回填缺陷链接、状态同步或最小化状态透传
- 明确平台问题对象与外部缺陷对象的映射关系

#### 模块 D：CI/CD 集成

- 支持从流水线触发任务或查询门禁结果
- 支持将门禁状态作为流水线阶段输入
- 明确失败回传协议和超时策略

### 5.4.3 交付物定义

- 对接协议说明和字段映射文档
- 至少一条提测链路接通
- 至少一类 IM 通知链路接通（平台侧入口已完成：`im_notify` / `feishu_bot` + IM/飞书 webhook/worker；真实 endpoint 仍需完成本地 smoke、2 小时试运行和 24 小时联调验收）
- 至少一类缺陷系统接通（已完成：`defect_sync` + issue defect lifecycle + Web/CLI worker 入口）
- 至少一类 `CI/CD` 门禁查询或回调能力（`sync-ci-admission-decisions` 已上线）
- 一份外部链路长时联调 runbook 和验收记录模板（已新增/更新：优先 IM/飞书链路，覆盖本地 mock/smoke、真实 2 小时试运行、真实 endpoint 24 小时、安全、receipt 反查、失败、dead-letter replay、订阅治理、验收和回滚）

### 5.4.4 依赖关系

- 依赖门禁中心、问题中心和协作中心的数据模型稳定
- 依赖鉴权机制、回调安全机制和接口限流能力
- 依赖平台对外 API 或事件机制

### 5.4.5 验收标准

- 典型提测流程可基于 CI 回传结果自动触发门禁判断（先支持 admission.override_recorded 单点）
- 关键决策回传可观测 delivery、重试、dead-letter 与 replay 运行态
- 本地 IM mock/smoke 可稳定验证 `im_notify` / `feishu_bot` 出站合同、worker 运行、receipt 持久化和 outbox 运维观测；该结果只作为进入真实飞书试运行的准入条件
- 真实 IM/飞书订阅方可稳定收到协作事件、准入结论和 outbox 告警，且消息合同固定为 `asl.im_notify.v1` 或飞书机器人格式
- P0 真实链路联调按 IM runbook 验收：真实 webhook 先稳定运行 2 小时并获得可接受噪声反馈，再至少稳定运行 24 小时；验签通过、幂等去重生效、consumer receipt 可回看、dead-letter 有分级和 replay 记录，通知噪声可被接受。未完成真实 24 小时前，不把 IM/飞书写成真实外部链路已完成
- 阻塞型问题可一键或半自动创建缺陷，并能回填缺陷链接、同步外部状态；若未达到可关闭状态，平台问题不能直接关闭
- 流水线可根据门禁结果继续或阻断后续步骤

### 5.4.6 主要风险

- 外部系统字段不统一，导致适配复杂度高
- 通知策略不当会带来告警疲劳
- 回调或接口失败时缺少补偿机制会影响流程可靠性

## 5.5 阶段 5：Web 主入口（已完成一部分，已落地首页/任务/问题/巡检/准入/Golden Suite 入口、结构化准入报告摘要与产物跳转、runner 摘要卡与下钻、问题协作动作和准入人工覆盖入口，以及团队共享入口模式/平台说明页/平台与 ready API/正式 API manifest/OpenAPI 风格描述/回调安全边界、请求级边界头、受信 SSO header 最小接入、只读用户目录和责任检索 API，仍缺完整多用户鉴权、团队级设备调度入口、完整对外报告发布流和更多平台动作）

### 5.5.1 阶段目标

建立统一 Web 使用入口，承接任务、问题、门禁和协作访问，降低对本地工具和临时脚本的依赖。

当前开发状态：

- 已落地页面：`/`、`/tasks`、`/issues`、`/runner`、`/goldens`、`/admission`
- 已落地下钻：golden case 详情、golden suite diff、准入详情、baseline history、报告/审计/comparison 产物跳转
- 已落地巡检只读页：`/runner` 和 `/api/runner` 可直接查看 patrol runner 的锁状态、运行心跳、最近 patrol 摘要、最近几轮 patrol 历史、失败轮次快速过滤、异常轮次详情展开、一键跳转、最新心跳关联提示、任务影响范围提示、异常严重度分层、严重度过滤和基础路径信息
- 已落地首页巡检摘要卡：首页已把 runner 的 `status / lock_state / heartbeat age / cycle_count / 最近一轮 patrol 摘要` 前置到摘要卡里，并对异常态做高亮提示、操作建议和可直接点击的动作入口
- 已落地 Golden Diff 排查能力：`change_type` / `changed_field` / `case_id` 过滤、左右 case 的最小字段对比摘要，以及 `baseline_rules / candidate_rules / filters / expected` 四个关键块的折叠式摘要
- 已落地状态与排查辅助：准入状态摘要条、点击下钻、缺失态建议、history 过滤与详情折叠
- 已落地准入报告页面摘要与产物跳转：准入详情页可展示当前报告、`AdmissionCase`、golden suite、latest audit、comparison report、baseline history 和最近版本索引，并通过 `/admission/view?path=...` 打开本地报告/审计/对比产物
- 已落地最小 Web 操作入口：问题认领、评论、状态流转、准入人工覆盖
- 已落地规则配置入口的阶段形态：以只读配置中心展示规则来源/默认规则/生效规则，并提供候选编辑预览和后续校验、diff、回放、评审引导；规则文件仍本地管理，不是完整在线规则编辑器
- 已落地团队共享入口模式：`serve-web` 已支持 `--portal-mode team_entry --public-base-url ...`，可把当前 portal 明确声明为共享团队入口，而不再只是一台机器上的临时控制台
- 已落地平台说明与就绪检查：新增 `/platform`、`/api/platform` 和 `/ready`，用于统一展示部署模式、共享入口、页面/API 清单、关键服务 readiness 和写操作边界
- 已落地正式 API 描述入口：新增 `/api/manifest` 与 `/api/openapi.json`，用于统一暴露读写端点、响应边界、回调合同和共享入口对接口径
- 已落地请求级边界元数据：所有 HTTP 响应现在会带稳定 `X-Request-ID / X-ASL-Request-ID / X-ASL-Portal-Mode`，并补入基础安全响应头，写操作审计可稳定串起 request id、identity 与 audit event
- 已落地回调安全边界：非本地 webhook 现在要求 `https + signing_secret`，并统一暴露 callback contract、signature headers、idempotency key、failure policy 与 key rotation 元数据
- 已落地受信 SSO header 最小接入：Web/API 写操作可优先解析 `X-ASL-SSO-Provider / X-ASL-External-Subject / X-ASL-External-Email / X-ASL-Org / X-ASL-Team / X-ASL-Role`，审计中记录 auth mechanism、identity provider、external subject、external email、organization、team 和 request id
- 已在 `/platform` 和 `/api/platform` 暴露 `identity_capabilities`，明确当前支持 `local_session` 与 `trusted_sso_header`
- 已落地只读用户目录与责任检索 API：新增 `/api/users` 和 `/api/responsibility`，前者优先读取服务层 user profile、失败时回退本地 actor，后者汇总 actor/profile、外部身份、issue/admission/defect/release 等对象上的责任线索
- 当前已进入“团队共享入口边界”阶段：查看者默认看到同一份平台数据，写操作继续通过服务端解析 identity 并留痕；正式开放 API、最小回调安全边界、正式在线身份边界的最小接入形态和最小只读目录/责任视图已部分完成；设备治理目前只在首页/任务/runner 中提供状态、目标设备、主备设备、隔离和恢复摘要，不是完整团队设备调度入口
- 当前 Web 中的版本测试报告 / 准入报告按结构化摘要、API payload 和本地产物跳转验收，不是完整对外 PDF 渲染、邮件分发或签核审批流
- 当前仍不是多租户平台，也不是完整团队级设备池：没有按不同用户或团队隔离设备可见性，也没有预约、配额、审批、排班或维护窗口工作流；需要共享时仍优先通过本地部署页面、报告、JSON 和产物导出给别人看
- 尚未落地更正式的平台动作，例如基线变更审批、统一待办、消息中心、跨系统回写和完整多用户鉴权
- 尚未落地团队级设备调度入口，例如设备日历、借用/释放流程、团队配额、冲突处理、维护窗口和设备责任人视图

当前重点能力状态矩阵：

| 能力 | 当前状态 | 已可依赖内容 | 不建议依赖内容 |
| --- | --- | --- | --- |
| IM/飞书 | 部分可用 | `im_notify` / `feishu_bot` 平台侧入口、消息合同、worker、本地 mock/smoke、receipt/outbox 运维观测和真实联调 runbook | 未完成 24 小时真实联调前，不作为真实生产通知链路或完整订阅降噪能力 |
| SSO/身份 | 部分可用 | 本地 session、受信 SSO header claims、写操作 identity 解析、审计增强、只读用户目录和责任检索 | 完整企业级 OIDC/LDAP/SSO、独立 IAM、多租户隔离、复杂组织权限和自动责任同步 |
| 设备调度 | 部分可用 | 本地无人值守 runner、主备设备、轮转、候补/空闲池补位、隔离、恢复探测和状态摘要 | 团队级设备预约、配额、审批、排班、维护窗口、设备日历和跨团队治理 |
| 规则在线发布 | 不建议依赖 | 只读规则配置中心、候选编辑预览、校验、diff、回放、评审和基线审计 | 在线保存、发布、审批、灰度、回滚和多级规则变更平台 |

### 5.5.2 重点任务拆分

#### 模块 A：Web 首页

- 展示平台总体运行状态、当日异常、门禁结果和待处理事项
- 提供常用入口和关键告警概览

#### 模块 B：任务大厅

- 展示任务列表、执行状态、运行历史和失败概览
- 支持按应用、版本、场景、设备组筛选

#### 模块 C：问题中心

- 展示聚合问题、Top Issue、回归问题和待处理问题
- 支持查看关联报告、证据、评论和流转状态

#### 模块 D：准入中心

- 展示准入结论、规则命中明细、人工确认状态和审计记录
- 支持从准入结果追溯到问题、分析快照和执行任务

### 5.5.3 交付物定义

- Web 信息架构与导航方案
- 首页、任务大厅、问题中心、准入中心页面
- 与后台服务联调完成的 API 列表
- Web 入口使用手册或演示材料

当前已落地的首版交付：

- `python -m stability.cli serve-web --host 127.0.0.1 --port 8030`
- 页面：`/`、`/platform`、`/tasks`、`/issues`、`/runner`、`/goldens`、`/admission`，以及 golden case 详情页 `/goldens/case/<case_id>`、golden suite diff 页 `/goldens/diff`、准入详情页 `/admission/baseline/<baseline_key>` 和产物跳转页 `/admission/view?path=...`
- JSON 端点：`/api/platform`、`/api/home`、`/api/tasks`、`/api/issues`、`/api/users`、`/api/responsibility`、`/api/runner`、`/api/goldens`、`/api/goldens/case/<case_id>`、`/api/goldens/diff`、`/api/admission`、`/api/admission/baseline/<baseline_key>`、`/api/integration/outbox`、`/ready`、`/health`
- 身份入口：`/platform` 与 `/api/platform` 会展示 `identity_capabilities`；完全没有 SSO header 时，本地 session / `X-ASL-Actor` 路径仍可用；SSO header 不完整时，写操作应返回错误而不是静默降级
- 目录与责任入口：`/api/users` 提供只读用户 profile/actor 视图；`/api/responsibility` 提供只读责任线索汇总。它们用于责任检索和审计增强，不代表完整账号体系或跨系统自动同步已完成
- 当前页面直接复用持久化服务层数据：
  - 首页：设备摘要、最近任务/Run、Top Issue、准入基线概览
  - 任务大厅：任务定义和最近执行历史
  - 问题中心：聚合问题列表、影响面摘要，以及最小协作动作入口与当前处理状态
  - Golden Suite：正式样本库清单、layer/issue_type/expectation 统计、单 case 下钻，以及两份 suite 的只读 diff 视图，可直接查看 `added / removed / modified / unchanged` 摘要，并支持 `change_type`、`changed_field` 和 `case_id` 搜索/过滤；同时 diff 卡片会直接展示左右 case 的最小字段对比摘要，并为 `baseline_rules / candidate_rules / filters / expected` 提供折叠式关键块摘要，再跳转到左右 case 详情
  - 准入中心：规则评审基线、质量门禁摘要、latest 审计摘要、最近几版 latest 索引，以及单条基线的当前报告、golden suite、latest audit、comparison report、baseline history 时间线和版本索引下钻页；详情页顶部会汇总 `review / comparison / latest audit / golden suite` 状态，并支持点击状态块直接下钻到对应 section，同时给出缺失态/失败态的下一步操作建议，也支持 `action / comparison_only` 最小过滤、事件详情折叠和人工覆盖动作，并可直接跳转打开对应的 review report、comparison report 与 audit 产物；规则配置入口当前按只读配置中心和候选编辑预览理解，用于看清规则来源、生效内容和候选变更影响，不直接在线保存或发布规则
- 报告共享口径：当前 Web 主入口负责展示结构化准入报告摘要和打开本地 report/audit/comparison 产物；跨人共享仍优先使用本地部署链接、报告、JSON、HTML、Markdown 和运行产物导出，不按 PDF/邮件/审批流验收
- 演示与验证入口：`scripts/verify_web_portal_smoke.sh`

### 5.5.4 依赖关系

- 依赖前四个阶段的后台能力与数据接口基本稳定
- 依赖统一权限控制和身份接入；当前已具备本地 session / actor、受信 SSO header 最小边界、派生 user profile 和只读责任检索，完整企业级 SSO、IAM、自动责任同步和组织权限治理仍需后续建设
- 依赖基础前端框架、接口规范和发布流程
- 若启用受信 SSO header，依赖可信反向代理或网关注入并清洗外部同名 header

### 5.5.5 验收标准

- 主要角色可通过 Web 完成核心查看和处理动作
- 核心页面信息一致，能追溯至原始任务、问题和结论
- 页面性能和可用性满足团队日常使用
- Web 成为团队默认入口
- 本地部署仍可用，查看者默认看到同一份平台数据；身份主要约束写操作和审计
- 受信 SSO header 路径可为写操作提供 provider、external subject、organization、team 和 request id 审计信息，但不按完整企业级 SSO 验收
- `/api/users` 和 `/api/responsibility` 可用于只读目录查看、责任线索检索和审计增强，但不改变现有权限行为、责任写入或外部系统同步业务流

### 5.5.6 主要风险

- 后台能力未稳定前过早建设页面，容易反复返工
- 页面只做展示不做操作，无法支撑团队共享入口
- 数据接口口径不一致导致页面认知混乱
- 受信 SSO header 如果没有被上游可信代理清洗，可能被外部请求伪造；portal 只消费 trusted header，不负责源头防伪

## 6. 优先级

### 6.1 Must

- `7x24` 无人值守基本能力
- 质量门禁核心闭环
- Web 主入口基础版

### 6.2 Should

- 团队协作流转
- 提测平台、IM、缺陷系统、`CI/CD` 的核心集成链路

### 6.3 Could

- 更细粒度的通知订阅策略
- 更复杂的审批或放行策略
- 更灵活的页面定制与大盘展示

## 7. 建议推进顺序

建议按以下顺序推进，以降低返工和空壳化风险：

1. 先补无人值守底座，确保平台具备持续运行能力
2. 再建设质量门禁，让分析结果转化为流程结论
3. 再补协作流转，保证问题和结论有人跟进
4. 再接外部系统，将平台接入提测、通知和发布链路
5. 最后统一收口到 Web 主入口，作为团队默认使用界面

不建议先做完整 Web 壳子再回填后台能力，否则容易形成“能看不能用”的平台外观。

## 8. 里程碑建议

### 8.1 里程碑 M1：无人值守可试运行

- 可启动长周期任务
- 支持基础恢复、补位和隔离
- 具备值班或巡检视角

### 8.2 里程碑 M2：门禁可参与提测决策

- 关键规则已有本地文件配置、只读配置中心和候选编辑预览；完整在线保存/发布/审批仍属后续治理
- 典型场景可自动生成准入结论
- 支持人工确认和审计

### 8.3 里程碑 M3：协作与集成打通

- 问题可认领、评论和流转
- 至少一条外部提测或缺陷链路接通
- 至少一类通知能力可用

### 8.4 里程碑 M4：Web 作为统一主入口

- 首页、任务大厅、问题中心、准入中心可稳定使用
- 核心角色日常操作可转移到 Web

## 9. 研发、测试与项目管理拆分建议

### 9.1 研发拆分建议

- 先拆后台核心对象与状态机，再拆页面和交互
- 以“运行中心、门禁中心、协作中心、集成中心、Web 前端”分小组或分模块推进
- 对外集成统一走接口层或事件层，避免业务逻辑散落

### 9.2 测试拆分建议

- 单独建设长稳验证、故障注入和恢复验证方案
- 单独建设门禁规则验证样例库
- 单独建设权限、审计、通知和接口回调验证清单
- Web 侧补充关键路径回归和角色视角用例

### 9.3 项目管理拆分建议

- 将 `V3` 按五个阶段拆里程碑，按阶段进行评审和验收
- 将跨团队依赖提前锁定，例如提测平台、缺陷系统、IM、`CI/CD`
- 对“必须上线能力”和“建议补齐能力”做版本内分层，避免范围膨胀

## 10. 主要风险与应对

| 风险 | 说明 | 建议应对 |
| --- | --- | --- |
| 底层稳定性不足 | `V1 / V2` 不稳会导致 `V3` 流程能力失真 | 先做稳定性准入，不满足条件不推进上层闭环 |
| 门禁误判 | 错误结论会直接影响团队信任 | 保留人工确认与审计机制，逐步提升自动化比例 |
| 集成复杂度高 | 外部系统差异大、排期不可控 | 先打通一条最关键链路，再做通用化 |
| Web 提前空壳化 | 页面先行但后台能力不齐 | 按后台闭环成熟度分批开放页面 |
| 通知噪声过高 | 过量通知会影响接受度 | 默认最小化通知，支持按角色和应用订阅 |

## 11. 建议与可选实施

以下内容属于建议或可选实施，不作为 `V3` 必须一次性完成的硬性交付：

- 建议优先建设最小权限模型，不在首版引入过细角色体系
- 建议先接一类 IM、一类缺陷系统、一类 `CI/CD`，避免集成面过大
- 建议先上线基础首页和核心中心页，再逐步补充高级筛选和自定义看板
- 建议为门禁规则和恢复动作保留灰度开关，降低误伤范围
- 可选实施长期运行专项看板、值班报表和恢复动作效果分析

## 12. 版本验收结论建议

`V3` 可以视为达到版本目标，至少应满足以下条件：

- 平台已具备稳定的无人值守运行基础能力
- 关键场景可产出可追溯的准入结论
- 团队可在平台内完成基础协作处理
- 至少一条外部链路真实接入团队流程
- Web 已成为团队查看和处理核心信息的主入口

若上述条件仅部分满足，则更适合定义为 `V3` 阶段性里程碑达成，而非完整版本闭环达成。

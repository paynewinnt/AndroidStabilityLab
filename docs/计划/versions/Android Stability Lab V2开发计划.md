# Android Stability Lab V2 开发计划

## 1. 文档目标

本文档用于承接主文档《`Android Stability Lab开发计划`》中第 5 章 `V2` 开发计划，将版本范围展开为可执行、可拆分、可验收的独立计划，供研发、测试和项目管理继续细化。

`V2` 的核心目标不是扩展新的执行外壳，而是在 `V1` 已经形成的执行结果之上，建设稳定、可信、可复用的中心分析能力，打通聚合、对比、回归判断和初步归因闭环。

## 1.1 状态维护规则

- `V2` 任一阶段有实际开发落地后，必须在同一轮同步更新本文件对应阶段的标题状态短句和“当前开发状态”
- 更新时不能只改阶段正文，不改标题；也不能只改总计划摘要，不改本子计划
- 阶段标题应明确写出“当前状态 + 已落地内容 + 主要剩余缺口”，保证只看标题也能判断推进程度

## 2. 版本定位与边界

### 2.1 版本定位

`V2` 是从“执行闭环”走向“分析闭环”的关键版本，重点是把分散的任务结果、异常记录、性能数据和证据对象沉淀为可持续消费的分析资产。

### 2.2 版本边界

`V2` 聚焦以下范围：

- 问题指纹与聚合规则
- 分析快照与分析数据底座
- 问题中心、`Top Issue`、版本/设备/场景对比视图
- 回归阈值、回归判断与分析结论沉淀
- 基于规则的初步归因
- 扩展证据接入，如 `dropbox / dumpsys / perfetto`

`V2` 不进入以下边界：

- 不承担 `V1` 执行链路不稳定时的兜底修复主体工作
- 不扩展为 `V3` 的流程平台、准入中心、团队协作中心或 `Web` 主入口
- 不以复杂编排替代当前版本的分析主线

## 3. 前置条件与依赖

### 3.1 外部依赖

- `V1` 已具备稳定的任务、执行实例、异常、证据、报告基础模型
- 关键执行链路已有可复用的结果产出格式，至少能稳定提供任务维度和实例维度的数据
- 现有性能监控能力已纳入任务执行链路，能够按统一结构沉淀关键指标

### 3.2 版本内依赖

### 3.3 当前实现起点

当前代码已具备 `V2` 阶段 1 的最小切入点：

- 已有 `issue`、`artifact`、`run`、`instance` 的持久化模型
- 已有 `analysis_ready` 风格的实例摘要输入
- 已落地首版 `issue_fingerprint`、`analysis_service`
- 已提供 `list-top-issues` / `show-issue-group` CLI 作为最小分析入口
- 已落地 `comparison_service`，并提供 `compare-issues` CLI 作为版本 / 设备 / 场景三维的最小对比入口
- 已落地 `performance_trend_service`，并提供 `compare-performance-trends` CLI 作为关键性能指标趋势对比入口
- 已落地首版 `regression_service`，并提供 `judge-regression` CLI 作为最小回归判断入口
- `judge-regression` 当前已覆盖 issue 与关键性能指标两类回归判断，`regression` 快照也已同步固化两类结果
- 已落地首版本地规则配置文件，当前 `fingerprint`、`regression` 与 `attribution` 规则已从代码常量抽到本地配置，可版本化记录
- 已落地文件型 `snapshot_service`，并提供 `create-analysis-snapshot / list-analysis-snapshots / show-analysis-snapshot` CLI 作为最小分析快照入口
- 已补齐第一批治理动作：`show-analysis-rules / validate-analysis-rules / export-analysis-rules / diff-analysis-rules / replay-analysis-rules / review-analysis-rules` 与 `delete-analysis-snapshot / prune-analysis-snapshots`
- 已把规则治理消费口径同步到更正式的配置入口：当前应按只读查看规则来源、默认规则、生效规则，以及对候选规则做编辑预览、校验、diff、回放和准入评审引导来验收；规则文件仍由本地文件管理，不按在线保存/发布规则编辑器验收
- 已补入文件型“规则黄金样本 + 回放验收集”：`verify-rule-replay-golden-samples` 可直接跑固定 golden suite，当前 `v2` 套件已覆盖 `crash / anr / process_exit / startup_timeout / device_offline / reboot` 六类 replay 语义样本，并按 `merge_semantics / identity_semantics / stability_guard` 三层输出结果
- 已补入“真实 run -> 黄金样本草案”半自动工具：`draft-rule-replay-golden-sample --run-id ... --issue-id ... --output ...` 可从真实持久化 run 中抽取 issue 事件，自动生成一条带 `dataset / baseline_rules / candidate_rules / replay_preview / expected` 的黄金样本草案，降低沉淀真实样本的人工成本
- 已补入“draft -> 正式 golden suite”受控提升命令：`promote-rule-replay-golden-draft --source-path ... [--target-path ...] [--case-id ...] [--replace-existing]` 会在写入正式样本库前做结构校验、`case_id` 冲突检查，并对待提升 case 再跑一轮 acceptance，只有通过后才真正落盘
- 已补入“golden suite 清单与差异查看”命令：`list/show/diff-rule-replay-golden-samples` 可直接查看样本库清单、展开单条 case 的完整 payload，并对两份 suite 做 `added / removed / modified / unchanged` 差异比对，方便管理和回看样本资产
- 新创建的分析快照已开始记录 `source_refs`，可追溯来源 `task/run/instance/device`、报告路径、执行日志路径和证据路径；`show-analysis-snapshot` 也会返回完整性检查结果
- `replay-analysis-rules` 已可在同一批历史 run 样本上对比基线/候选规则对 `Top Issue` 聚合的影响，并区分 `regrouped / fingerprint_changed / count_changed / added / removed`
- `create-analysis-snapshot --snapshot-type replay` 已可把一次规则回放结果固化成快照，统一记录基线/候选规则版本、样本过滤范围、变化摘要和 `source_refs`，供后续规则评审、回归判断和审计复盘复用
- 已补入最小“规则变更准入”闭环：`review-analysis-rules` 会基于本地准入策略输出 `pass / conditional_pass / fail`，并自动附带一轮 golden suite 结果，把“真实历史样本回放 + 固定黄金样本验收”一起作为准入依据；`create-analysis-snapshot --snapshot-type review` 会把准入结论、命中发现、golden suite 结果、策略版本、样本范围和 `source_refs` 一并固化，便于规则评审、审计和回归复盘
- 已补入“规则评审报告汇总”能力：`create-rule-review-report` 可汇总多条 `review` 快照，统一输出结论分布、规则版本、基线/候选来源、高风险 family、golden suite 汇总以及 `JSON / Markdown / HTML` 报告，供规则变更评审会直接使用
- 已补入“规则评审报告对比”能力：`compare-rule-review-reports` 可对比两份已落盘的规则评审报告，输出 `snapshot / finding / changed family / decision_counts` 的 delta 以及高风险 family 的 `added / removed / changed / unchanged` 差异；现在 comparison summary 也会显式带上左右两侧的 golden suite 汇总与 golden suite delta
- 已补入“规则评审报告基线化”能力：`set/show-rule-review-report-baseline` 可把评审报告注册成命名基线，`compare-rule-review-report-against-baseline` 可直接把当前报告对比该基线；未显式指定基线键时，还可按 `policy_version / candidate_path` 自动回退到最近一次无 `fail` 的可接受报告
- 已补入“基线晋升规则”能力：`promote-rule-review-report-baseline` 会基于独立晋升策略评估当前报告相对基线是否允许晋升，只有通过策略检查后才会真正更新命名基线；当前首版策略已限制决策类型、总量 delta 和 family delta 类型，CLI 输出也会显式展示目标报告与当前基线报告各自的 golden suite 汇总
- 已补入“基线历史与回滚”能力：`list-rule-review-report-baseline-history` 可查看基线的完整 revision 历史，`rollback-rule-review-report-baseline` 可将命名基线回滚到上一个或指定历史报告版本，并把 rollback 事件继续写入历史
- 已补入“基线变更审计报告”能力：`create-rule-review-report-baseline-audit` 可把命名基线的完整历史固化成一份审计报告，统一输出 `who / when / from / to / why` 时间线，并优先复用历史中的 `reasons / comparison_id / policy_version` 元数据；当前摘要里也会显式带上“当前基线报告”的 golden suite 汇总
- 现在 `set / promote / rollback` 三类基线变更动作在成功后都会自动刷新该基线的 latest 审计产物，稳定落在 `runtime/analysis_review_report_baseline_audits/latest/<baseline_key>/`；同时还会维护 `index.json + versions/<revision_id>/` 轻量版本索引，便于直接回看最近几版 latest；首版保留策略默认保留最近 `10` 版，并额外保留 `promote / rollback` 关键审计版本；需要独立留档时，仍可额外执行 `create-rule-review-report-baseline-audit`
- 已补入“审计查看命令”：`show-rule-review-report-baseline-audit` 可直接查看某个基线当前 latest 审计摘要、保留策略以及最近几版索引，供日常规则值班或评审快速查看
- 已落地首版 `attribution_service`，并在 `show-issue-group` 中返回规则式初步归因结果、命中依据与置信度
- 已落地首批扩展证据接入，当前 issue 证据链已支持按问题类型最佳努力抓取 `dropbox / dumpsys meminfo / dumpsys SurfaceFlinger`
- 已落地首版业务遍历正式入口：`custom` 模板已支持 `uiautomator2 / adb_script / external_script` 三种接入模式，统一回写步骤时间线、失败摘要和附件路径，进入现有 Run / 报告 / 分析主链

这意味着 `V2` 当前不再是“从零开始设计聚合”，而是应继续围绕“聚合规则稳定化、跨维度对比、性能趋势、回归判断”推进。

- 没有稳定的问题指纹，就无法做可信聚合
- 没有可信聚合，就无法做 `Top Issue`、趋势和回归判断
- 没有分析快照，就难以对分析结论做复现、审计和对比
- 没有规则治理，归因和回归结论会迅速失真

### 3.3 准入条件

建议在 `V2` 启动前满足以下条件：

- `V1` 主流程已能稳定运行，并形成持续样本
- 关键异常类型已有基础命中率与误判率认知
- 附件存储、保留周期和引用方式已有基础约束

## 4. 总体建设思路

`V2` 的建设顺序建议遵循“先统一分析对象，再建立聚合规则，再做分析视图，再做回归判断，最后补初步归因和扩展证据”的路径，避免在数据基础不稳时直接上层视图和结论系统。

建议的分析能力建设顺序如下：

1. 统一分析对象和分析口径
2. 建立问题指纹、聚合规则和快照机制
3. 建立问题中心与核心对比分析能力
4. 引入回归阈值与回归判断
5. 补充规则式初步归因与扩展证据

## 5. 阶段计划

## 5.1 阶段 1：聚合底座（已完成一部分，已落地问题指纹、聚合、分析快照、规则治理/回放/准入、golden suite 管理、评审报告基线治理和只读规则配置入口口径，剩聚合规则稳定化、规则说明、在线发布治理与更细的快照保留策略）

### 当前开发状态

- 已落地首版 `issue_fingerprint`、`analysis_service`、`snapshot_service` 和本地规则配置
- 已落地规则治理、回放、评审、快照留档、评审报告汇总/对比、命名基线、晋升规则、历史回滚与 latest 审计
- 已同步更正式规则配置入口的阶段边界：当前是只读规则配置中心与候选编辑预览，负责展示源规则/默认规则/生效规则并引导校验、diff、回放和评审；实际规则文件仍保留本地管理
- 已落地 `golden suite` 全链路：固定验收集、真实 run 抽样 draft、受控 promotion、清单查看、单 case 展开和双 suite diff
- 当前剩余重点是聚合规则稳定化、规则说明沉淀、在线保存/发布/审批/回滚治理，以及快照/审计产物更细的保留策略

### 阶段目标

建立 `V2` 的分析基础设施，使执行结果能够被统一归档、聚合和复用，为后续视图、趋势和回归判断提供一致的数据来源。

### 任务拆分

- 梳理 `V1` 输出中的任务、实例、异常、证据、性能指标结构
- 定义分析对象模型，如问题、问题样本、问题快照、对比维度对象
- 建立问题指纹生成策略，明确异常类、堆栈类、日志类、性能类问题的首批口径
- 建立聚合规则，明确聚合键、近似匹配边界、版本兼容策略
- 建立分析快照机制，确保同一批次分析结果可追溯
- 建立性能趋势对比基础，明确指标口径、聚合周期和对比窗口

### 交付物定义

- 问题指纹规则初版
- 聚合规则与规则配置说明
- 分析对象数据结构说明
- 分析快照落盘/存储方案
- 关键性能指标趋势基础能力
- 规则回放、准入评审与评审报告汇总/对比/基线化/晋升规则/历史回滚基础能力
- 只读规则配置中心和候选编辑预览口径说明；规则快照导出、评审报告和 JSON/HTML/Markdown 产物仍作为共享主形态

### 完成标准

- 相同类型问题可稳定聚合到同一问题项
- 分析结果支持按批次或时间窗口追溯
- 至少一组关键性能指标可完成跨版本或跨场景趋势对比

## 5.2 阶段 2：分析视图（已完成一部分，已落地 Top Issue、版本/设备/场景对比、性能趋势对比与基础钻取 CLI，剩更正式的问题中心与排序治理）

### 当前开发状态

- 已落地 `list-top-issues / show-issue-group`
- 已落地 `compare-issues`，覆盖版本 / 设备 / 场景三个维度的最小对比
- 已落地 `compare-performance-trends`，可直接输出关键指标趋势对比
- 当前剩余重点是更正式的问题中心、排序治理和更强的分析消费视图

### 阶段目标

基于聚合底座输出面向研发和测试的核心分析入口，让问题能够被看见、被排序、被横向对比。

### 任务拆分

- 建立问题中心的数据查询和展示结构
- 建立 `Top Issue` 统计口径，如出现次数、影响范围、趋势变化
- 建立版本维度对比能力
- 建立设备维度对比能力
- 建立场景维度对比能力
- 统一分析筛选条件、排序规则和基础钻取路径

### 交付物定义

- 问题中心初版
- `Top Issue` 列表与排序规则
- 版本/设备/场景对比分析视图
- 基础钻取链路定义，从汇总结果进入样本与证据

### 完成标准

- 可从聚合问题进入对应样本和证据
- 可输出版本、设备、场景三个核心维度的差异结果
- `Top Issue` 排序结果具备可解释性，口径在文档中明确

## 5.3 阶段 3：回归分析（已完成一部分，已落地 issue/metric 回归判断、阈值配置外置、回归快照与准入联动，剩待人工复核状态与更完整结论治理）

### 当前开发状态

- 已落地 issue 与 metric 两类回归判断，以及统一的阈值配置外置
- 已落地 `judge-regression` 和 `regression` 快照，结论可回溯到规则、样本和快照
- 回归结论已能继续进入规则评审/准入链，作为后续治理输入之一
- 当前剩余重点是待人工复核状态和更完整的结论治理口径

### 阶段目标

在已有聚合和对比能力基础上，形成可沉淀、可复核的回归判断能力，支持版本演进过程中的质量比较。

### 任务拆分

- 定义回归分析对象和回归判断输入
- 为异常率、发生次数、影响范围、性能指标建立首批阈值策略
- 建立回归判断流程，区分自动判断和待人工复核状态
- 建立分析报告快照，保留某次回归结论的上下文
- 建立结论字段和原因说明结构，支持后续准入能力复用

### 交付物定义

- 回归阈值配置初版
- 回归判断规则初版
- 回归分析结果结构
- 分析报告快照模板

### 完成标准

- 对同一对比对象可稳定给出“无明显变化 / 疑似回归 / 明显回归”等基础结论
- 回归结论可回溯到对应阈值、样本和分析快照
- 至少覆盖关键异常与关键性能指标两个分析类别

## 5.4 阶段 4：归因与扩展证据（已完成一部分，已落地最小 evidence-aware 规则式初步归因、黑屏/freeze/system_server crash/watchdog 一等文本启发式识别与结构化 evidence、性能风险阈值配置对象注入和 scoped override、首批扩展证据 `dropbox / dumpsys meminfo / dumpsys SurfaceFlinger / perfetto`，并已补 SurfaceFlinger/dropbox/Perfetto 最小结构化 parser；剩外部阈值治理入口、真实标定、Perfetto 正式解码、多证据交叉确认、扩展证据策略细化与更高置信度归因；不是 AI 根因诊断）

### 当前开发状态

- 已落地首版规则式 `attribution_service`，可基于 issue title、summary、process、artifact path、metadata / evidence 等样本信号输出归因方向、命中依据、置信度和规则版本，具备最小 evidence-aware 解释
- 已新增 `freeze / black_screen / system_server_crash / watchdog` IssueType，`MonkeyIssueDetector` 可从 note/highlights/stdout/stderr/logcat/summary/metadata 等文本中按关键词识别 freeze、黑屏、画面无刷新、输入无响应、surface black、system_server crash、watchdog 等信号，并输出 `evidence_signals`、`confirmation_level` 等结构化 evidence，保留命中片段供人工复核
- 已在 `PerformanceTrendComparison` 中新增 `performance_risk_items`，并由 `performance_trend_service` 输出 `performance_oom_risk / performance_memory_growth / performance_frame_jank_regression` 三类默认阈值启发式风险项
- 性能风险主比较链路已支持 `PerformanceRiskThresholdConfig / Override / Match` 等配置对象注入，可按设备、包名、场景等 scope 覆盖阈值，并在风险项 detail 中输出 `threshold_source / matched_scope / threshold_values`
- 已补入首批扩展证据：`dropbox / dumpsys meminfo / dumpsys SurfaceFlinger / perfetto`
- 扩展证据已能进入 issue 证据链，并在报告与分析链路中被引用；SurfaceFlinger、dropbox、Perfetto 已具备最小结构化 parser，可把 `structured_evidence` 写入 artifact metadata，并回灌 `structured_artifact_evidence / evidence_signals / matched_sources / matched_fragments / confirmation_level`
- 当前剩余重点是从外部规则文件或页面治理入口加载性能阈值、真实样本标定、Perfetto 正式 trace 解码、截图内容识别、帧刷新/输入事件等多证据交叉确认、扩展证据策略细化与更高置信度归因

### 阶段目标

补齐分析闭环最后一层能力，让问题不仅能被发现和判断，还能得到初步解释与更强的诊断支持。当前阶段已具备规则式/文本启发式初步识别、结构化 evidence、结构化风险项、性能阈值 scoped override 和最小 evidence-aware 初步归因解释，但不应等同于生产级智能诊断或 AI 根因诊断。

### 任务拆分

- 建立首批规则式初步归因能力
- 明确归因规则输入，如异常类型、关键日志、设备条件、场景特征、artifact path、metadata 和结构化 evidence
- 建立黑屏/freeze/system_server crash/watchdog 等高级异常的首批文本启发式识别规则，并保留结构化 evidence 与命中证据片段
- 建立 OOM、内存上涨、卡顿/帧耗时恶化的首批性能风险启发式规则
- 建立性能风险阈值配置结构，并接入按设备、包名、场景覆盖的主链应用
- 后续补齐性能阈值从外部规则文件或页面治理入口加载，以及基于真实样本的阈值标定
- 扩展接入 `dropbox / dumpsys / perfetto` 等补充证据，并沉淀最小结构化 parser 摘要
- 建立扩展证据与问题样本的关联关系
- 明确规则命中解释和低置信度展示方式
- 后续补齐截图内容识别、Perfetto 正式解码、帧刷新、输入事件等多证据交叉确认，以及性能阈值治理入口与真实标定

### 交付物定义

- 初步归因规则集
- 高级异常文本启发式识别规则与结构化 evidence 字段
- 性能风险项输出字段、默认阈值口径、阈值来源、命中 scope 与阈值配置结构
- 扩展证据采集与最小结构化 parser 接入说明
- 问题样本与扩展证据关联能力
- 归因结果展示字段定义

### 完成标准

- 至少覆盖首批高频问题类型的规则式归因
- 归因输出能展示方向、命中规则、命中字段、证据片段、置信度和规则版本，作为排查入口而非自动根因结论
- 黑屏/freeze/system_server crash/watchdog 可通过文本启发式形成初步 issue 记录，并保留结构化 evidence、artifact parser 摘要与命中片段供人工复核
- OOM、内存上涨、卡顿/帧耗时恶化可在 performance comparison payload 中形成结构化风险项，并标注当前阈值来源、命中 scope 与阈值值
- 分析人员可从问题样本查看关联扩展证据
- 归因结果与原始样本、规则命中信息可关联追溯
- 若只依赖文本启发式、最小 parser、默认阈值或尚未外部治理/真实标定的配置，应明确标记为“初步识别/启发式风险/规则式初步归因”，不能按完整根因诊断或 AI 根因诊断验收

## 6. 任务分解建议

为便于研发和测试继续拆分，建议按以下工作流分工：

### 6.1 数据与模型

- 分析对象模型定义
- 问题指纹与聚合键设计
- 快照结构定义
- 阈值与规则配置结构

### 6.2 分析引擎

- 指纹生成实现
- 聚合引擎实现
- 趋势计算与对比计算实现
- 回归判断与归因规则执行

### 6.3 证据与存储

- 扩展证据接入
- 样本与证据引用关系
- 快照与附件保留策略
- 性能指标时序存储与查询优化

### 6.4 展示与消费

- 问题中心接口与展示
- `Top Issue` 接口与展示
- 版本/设备/场景对比展示
- 回归结果和分析快照展示

### 6.5 测试与治理

- 指纹命中准确性验证
- 聚合误合并/漏合并验证
- 回归判断准确性验证
- 规则治理与回归样本集维护

## 7. 优先级

### 7.1 Must

- 问题指纹与聚合
- `Top Issue`
- 版本/设备/场景对比
- 回归结论
- 关键性能指标趋势分析

### 7.2 Should

- 业务遍历接入（已完成首版 `custom` 模板接入，后续重点转向路径库和更深监控联动）
- 初步归因
- 分析快照

### 7.3 Could

- 更复杂的场景编排
- 更细粒度性能退化分析

## 8. 建议推进顺序

建议按以下顺序推进，以减少返工：

1. 先统一分析对象、问题指纹和聚合规则
2. 再补分析快照与趋势基础
3. 再建设问题中心和 `Top Issue`
4. 再做版本/设备/场景对比
5. 再引入回归阈值与回归判断
6. 最后补初步归因和扩展证据

建议：

- `Top Issue` 和对比视图应建立在同一套聚合结果之上，避免口径分叉
- 回归判断不要早于聚合规则稳定，否则阈值会频繁失效

## 9. 交付物清单

`V2` 建议至少形成以下可交付成果：

- 独立的分析对象与规则文档
- 可运行的问题指纹与聚合能力
- 问题中心与 `Top Issue` 核心视图
- 版本/设备/场景对比能力
- 回归判断能力与分析快照
- 首批规则式初步归因
- 扩展证据接入说明与基础接入实现
- 对应测试清单、验证样本和验收记录

## 10. 验收标准

### 10.1 功能验收

- 执行结果可被统一沉淀到分析对象中
- 相似问题可按规则稳定聚合
- 用户可查看 `Top Issue` 并按版本/设备/场景完成对比
- 系统可输出基础回归结论，并保留快照
- 首批高频问题具备初步归因和扩展证据支撑

### 10.2 数据与准确性验收

- 聚合结果的误合并率和漏合并率处于可接受范围
- 回归判断对典型样本具备基础可信度
- 性能趋势口径稳定，重复计算结果一致

### 10.3 工程验收

- 核心规则具备配置化或可维护入口
- 分析链路有基础日志、失败定位和回放能力
- 关键接口或模块具备基础自动化测试

## 11. 主要风险

- `V1` 数据质量不稳定，导致聚合和回归失真
- 问题指纹设计过粗，导致误合并；设计过细，导致无法聚合
- 规则增长过快但缺乏治理，导致分析结论不可信
- 附件和扩展证据体量过大，造成存储和查询压力
- 性能指标口径不统一，导致趋势和回归判断摇摆

## 12. 风险应对建议

- 先建立样本集和回放机制，再扩充规则数量
- 先覆盖高频、稳定的问题类型，再处理复杂长尾问题
- 对回归结论保留“待确认”状态，避免过早绝对化
- 对大附件建立留存分级策略，避免拖垮分析链路

建议/可选实施：

- 可单独维护“规则变更记录”与“样本基线集”，用于后续 `V3` 准入规则复用
- 可提前预留分析事件埋点，为后续 `Web` 化与协作流转做准备，但不作为 `V2` 的主交付范围

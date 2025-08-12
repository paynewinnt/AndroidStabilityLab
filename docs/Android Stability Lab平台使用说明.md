# Android Stability Lab 平台使用说明

## 1. 平台一句话介绍

`Android Stability Lab` 是一个面向 Android 客户端稳定性测试、结果查看、问题分析和质量准入的本地优先平台：你可以用它下发任务、执行测试、查看 Run/问题/性能采样结果，并在需要时做准入判断与本地集成回传。

这份文档面向“平台使用方”编写，重点回答：

- 这个平台到底能干什么
- 我应该从哪里开始
- 我该用 Web、CLI 还是 API
- 一次任务从创建到看结果，最短怎么走
- 出问题时先查什么

说明：

- 以下内容以当前仓库代码为准
- 如果某些能力仍在建设中，会明确标注
- 如有少量地方无法从仓库直接确认，我会标注“根据当前代码推断”

## 2. 解决什么问题

这个平台主要解决 Android 稳定性工作里四类常见问题。

### 2.1 任务执行分散

很多团队平时会遇到这些情况：

- 任务靠人手工敲 `adb` 命令或个人脚本
- 同一类测试每个人执行方式不同
- 执行过一次之后，很难复用和追溯

这个平台把“任务定义 -> 创建 Run -> 执行 -> 结果落盘”收成同一条主链。

### 2.2 结果难看、难追、难比较

很多时候不是“没跑”，而是“跑了但看不懂”：

- 失败样本散落在日志、附件、截图、trace 里
- 同一个问题在不同设备/版本/场景里重复出现，但没人能快速看出是不是同源问题
- 性能采样有时候采到了，有时候没采到，团队不知道该去哪里看

这个平台提供了：

- `Run` 详情
- `Top Issue` 问题聚合
- `/performance` 性能采样页
- 回归比较与准入入口

### 2.3 长稳巡检和值班成本高

如果你们有周期性巡检、无人值守任务或每天/每周汇总需求，平台已经提供：

- unattended 任务配置
- patrol runner
- 日报 / 周报
- `/runner` 状态页

这适合本地值班和本机排查。

### 2.4 质量门禁没有统一入口

当前仓库已经有：

- `Quality Gate`
- `AdmissionCase`
- 人工覆盖
- 最小协作动作
- CI 回传链路

所以它不只是“把测试跑完”，还在逐步变成“把版本质量结论说清楚”的平台。

## 3. 适合哪些用户 / 角色

当前平台更适合下面这些使用者。

### 3.1 客户端测试 / 稳定性测试同学

适合做：

- 创建测试任务
- 执行 Run
- 查看失败原因
- 汇总近期问题
- 看性能采样是否采到

### 3.2 客户端开发 / 质量负责人

适合做：

- 查看某次 Run 的结果和证据
- 看 Top Issue 是否收敛
- 看是否存在明显回归
- 查看准入结论和人工覆盖记录

### 3.3 值班 / 巡检使用方

适合做：

- 看 runner 是否还在跑
- 看最近一轮巡检是否异常
- 看每日 / 每周摘要
- 看设备掉线、隔离、失败率

### 3.4 自动化 / 平台对接使用方

适合做：

- 通过 CLI 定时跑任务
- 调用 JSON API 做只读集成
- 使用 outbox / webhook 做本地回传

## 4. 平台核心概念说明

这一节尽量不用内部黑话，只解释用户真正会碰到的概念。

### 4.1 任务（Task）

任务是“你想让平台做的一类测试定义”。

一个任务通常会包含：

- 任务名：`--task-name`
- 目标包名：`--package-name`
- 模板类型：`--template-type`
- 目标设备：`--device`
- 可选的任务参数：`--task-params`
- 可选采样配置：`--sampling-interval`、`--metric`

根据当前代码，任务模板类型至少包括：

- `monkey`
- `cold_start_loop`
- `foreground_background_loop`
- `install_uninstall_loop`
- `reboot_loop`
- `standby_wake_loop`
- `custom`

长稳运行当前不是一个独立的 `template_type`。更准确的理解是：平台已经具备最小长稳模板族画像和配置建议，可以把上面这些模板按目标场景组合到无人值守任务中，再复用轮转、补位、隔离恢复、巡检摘要和日报/周报；但它仍偏“配置建议 + 运行画像”，不是完整长稳产品化入口。

其中 `custom` 现在不是“留空自己处理”的占位模板了。根据当前代码，它已经支持：

- `automation_mode=uiautomator2`
- `automation_mode=adb_script`
- `automation_mode=external_script`

这三类模式都会把步骤时间线、成功/失败状态、失败摘要和附件路径继续挂回 Run 结果里，方便后续统一分析。

对应 CLI：

```bash
./.venv/bin/python -m stability.cli create-task --help
```

### 4.2 Run

`Run` 是“某个任务被真正执行的一次实例”。

常见理解方式：

- `Task` 是模板
- `Run` 是执行记录

用户平时最常看的就是：

- `list-runs`
- `show-run`
- Web 的 `/tasks`
- Web 的 `/runs/<run_id>`

### 4.3 Admission / Quality Gate

这部分是“质量门禁 / 准入判断”。

根据当前代码，平台已经有：

- `QualityGate`
- `AdmissionCase`
- 结构化准入 report payload
- Web/API 准入报告摘要
- 自动结论
- 人工覆盖
- 最终结论
- case 证据链 `case_trace`

如果你不熟悉这两个词，可以先这样理解：

- `Quality Gate`：系统自动算出来的质量判断结果
- `AdmissionCase`：围绕某个基线/报告形成的一张“可追溯准入单”

用户可看到的常见字段包括：

- `final_decision`
- `error_code`
- `final_review_opinion`
- `top_issues`
- `performance_risk_items`
- `scenario_coverage`
- `case_trace`
- `source_refs`
- `ci_contract`
- `latest audit / comparison report / baseline history`

对应入口：

- CLI：`list-admission-cases`、`show-admission-case`
- Web：`/admission`、`/admission/baseline/<baseline_key>`、`/admission/view?path=...`
- API：`/api/admission`、`/api/admission/baseline/<baseline_key>`、`/api/admission/cases`

当前“版本测试报告 / 准入报告”的准确口径：

- 已经可以通过结构化 payload、Web 页面摘要和 JSON API 查看准入报告所需的核心信息，包括质量门禁结论、证据链、来源引用、人工覆盖、latest audit、comparison report 和最近版本索引
- 需要共享时，优先使用本地部署页面链接、报告产物、JSON、HTML、Markdown 和运行产物导出
- 这还不是完整对外 PDF 报告、邮件自动分发或多级签核审批流；如果团队需要这类正式发布流程，需要另行建设

规则配置入口的当前口径：

- 已有更正式的只读规则配置中心和候选编辑预览，适合查看规则来源、默认规则、生效规则，以及预览候选规则变更后的校验、diff、回放和准入评审影响
- 它不是完整在线规则编辑器；规则文件仍建议在本地仓库或本地部署环境中管理
- 需要共享时，优先导出规则快照、评审报告、JSON/HTML/Markdown 报告和运行产物，而不是依赖多人在线编辑同一份规则

### 4.3.1 高级异常识别口径

当前平台已经能把部分高级异常信号纳入统一问题和准入辅助信息：

- 初步归因建议：问题聚合下钻中的 `attribution` 是规则式结果，会基于 issue title、summary、process、artifact path、metadata / evidence 等样本信号输出归因方向、命中规则、命中字段、证据片段、置信度和规则版本。它具备最小 evidence-aware 解释能力，但只是排查入口和线索汇总，不是 AI 根因诊断。
- 黑屏 / freeze / system_server crash / watchdog：基于 note、highlights、stdout、stderr、logcat、summary、metadata 等文本信号做一等启发式识别，并输出 `evidence_signals`、`confirmation_level` 等结构化 evidence，保留命中片段供人工复核。
- OOM、内存上涨、卡顿 / 帧耗时恶化：在性能趋势对比结果中输出结构化 `performance_risk_items`，主链已支持 `PerformanceRiskThresholdConfig` 配置对象注入和按设备、包名、场景等 scoped override，风险项 detail 可展示 `threshold_source / matched_scope / threshold_values`。
- 扩展证据：`dropbox / dumpsys meminfo / dumpsys SurfaceFlinger` 等证据可进入 issue 证据链并被报告或分析链路引用。

这仍不是完整智能诊断，也不是 AI 根因诊断。截图、SurfaceFlinger 状态、帧刷新、输入事件等多证据交叉确认，以及性能阈值从外部规则文件或页面治理入口加载、真实样本标定，仍属于后续增强项。日常使用时建议把这些结果当作“风险提示和排查入口”，不要直接替代人工根因判断。

### 4.4 协作 / actor / identity

这部分当前已经存在，但请按“本地协作留痕”理解，不要把它想成互联网产品里的账号系统。

根据当前代码：

- 平台支持 issue / admission 的最小协作动作
- 包括认领、评论、状态流转、人工覆盖
- 服务端会解析本地 actor/session，并记录审计字段
- 如果部署在可信反向代理或网关后，也可以消费受信 SSO header，用于写操作身份解析和审计增强
- `/api/users` 可以只读查看由本地 actor 和外部身份派生出的用户 profile
- `/api/responsibility` 可以只读查看 issue、admission、defect、release 等对象上的责任线索汇总

但要特别注意：

- 当前平台不是“不同用户看到不同数据”的在线多租户系统
- 当前仍支持本地部署和本地 session / actor 路径
- 如果要给别人看，推荐导出报告、JSON 或运行产物
- 受信 SSO header 必须由可信反向代理或网关注入，并清洗外部请求里的同名 header

也就是说，这里的 actor / identity 主要解决的是：

- 谁做了写操作
- 谁做了评论或覆盖
- 谁触发了某次本地协作动作
- 如果启用了受信 SSO header，审计里还能记录 provider、external subject、organization、team 和 request id
- 如果需要排查责任归属，可以用 `/api/users` 和 `/api/responsibility` 做检索和审计增强

而不是为了做完整账号体系、复杂组织级权限管理或真正跨系统自动同步。

### 4.5 通知 / 集成 / outbox

这一块已经有最小闭环。

根据当前代码，平台已经支持：

- 本地 outbox 事件
- webhook 注册
- 投递重试
- dead-letter replay
- delivery worker
- CI 回调链路

更直白地说：

- 平台内部做出的某些动作，可以作为事件往外发
- 当前已经有一条比较明确的外部链路：CI 准入决策回传

当前入口包括：

- CLI：`deliver-integration-outbox`
- CLI：`run-integration-outbox-worker`
- CLI：`run-ci-admission-sync-worker`
- CLI：`sync-ci-admission-decisions`
- Web / API：`/api/integration/outbox`

## 5. 用户能完成什么事情

按照当前仓库，我建议把平台能力分成三类来理解。

### 5.1 已经可用的能力

以下能力已经可以直接给平台使用方用：

- 创建设备相关测试任务
- 创建并执行 Run
- 查看 Run 结果和详情
- 查看问题聚合与 Top Issue
- 查看最近性能采样和监控 backend
- 配置和查看无人值守巡检
- 查看 runner 心跳、最近巡检、日报和周报
- 查看 Golden Suite 和准入中心
- 查看 `AdmissionCase`、质量门禁、人工覆盖结果
- 查看规则配置中心，预览候选规则变更影响
- 通过 CLI / Web / JSON API 查询主要结果

### 5.2 正在建设中的能力

以下能力已经有骨架，但不建议把它理解成“完全成熟的平台能力”：

- Admission 协作闭环的进一步扩展
- 更完整的外部系统集成
- 更正式的在线身份/权限体系
- 规则在线保存、发布、审批和回滚治理
- 更长期运行的外部通知链路

### 5.3 暂不建议用户依赖的能力

以下能力目前不建议按“团队正式平台能力”依赖：

- 把当前 Web 当成面向全团队外放的正式在线平台
- 依赖当前本地 actor/session 机制做组织级权限控制
- 同时依赖多条外部 webhook 链路做复杂运营编排

原因很简单：当前仓库更明确地偏向“本地部署 + 本机使用 + 必要时导出共享”。

## 6. 用户如何使用

## 6.1 最推荐的使用入口

如果你是第一次接触这个平台，我建议这样选入口：

### 推荐顺序

1. Web：日常查看、判断、排查最直观  
2. CLI：创建任务、执行任务、自动化、精确查询  
3. API：给脚本或系统做只读集成  

### 为什么这样推荐

- Web 更适合“先搞明白平台里现在有什么”
- CLI 更适合“明确知道自己要跑什么”
- API 更适合“系统接系统”，不适合第一次上手

## 6.2 各入口差异

### Web

适合：

- 看首页概况
- 看任务和 Run
- 看性能采样
- 看问题中心
- 看 runner 状态
- 看 Golden / Admission
- 看规则配置中心和候选编辑预览

当前主要页面：

- `/`
- `/tasks`
- `/performance`
- `/issues`
- `/runner`
- `/goldens`
- `/admission`
- `/json-api`

### CLI

适合：

- 创建任务
- 创建 Run
- 执行 Run
- 配置无人值守
- 精确查询某个对象
- 查看、校验、导出、diff、回放和评审本地规则文件
- 集成 / 回放 / delivery worker

### API

当前更偏只读和自动化集成，主要端点包括：

- `/api/home`
- `/api/tasks`
- `/api/performance`
- `/api/issues`
- `/api/runner`
- `/api/goldens`
- `/api/admission`
- `/api/admission/cases`
- `/api/integration/outbox`

根据当前代码推断：

- API 里已经存在少量 POST 协作动作
- 但对普通平台使用方来说，不建议把 API 当作主入口

## 6.3 从创建任务到查看结果的最短路径

这是最短可执行路径。

### 第一步：确认设备

```bash
adb devices
./.venv/bin/python -m stability.cli list-devices --sync
```

### 第二步：创建任务

示例：

```bash
./.venv/bin/python -m stability.cli create-task \
  --task-name "首页冷启动稳定性检查" \
  --package-name "com.example.app" \
  --template-type cold_start_loop \
  --device emulator-5554 \
  --created-by cli \
  --sampling-interval 5 \
  --metric cpu \
  --metric memory \
  --task-params '{"loop_count": 10}'
```

你会得到一个 `task_id`。

### 第三步：创建 Run

```bash
./.venv/bin/python -m stability.cli create-run \
  --task-id <task_id> \
  --requested-by cli
```

你会得到一个 `run_id`。

### 第四步：执行 Run

```bash
./.venv/bin/python -m stability.cli execute-run \
  --run-id <run_id> \
  --monitoring-backend solox
```

如果你只想先验证链路，也可以不指定 backend，走默认路径。

### 第五步：看结果

CLI：

```bash
./.venv/bin/python -m stability.cli show-run --run-id <run_id>
```

Web：

```bash
./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

打开：

- [首页](http://127.0.0.1:8030/)
- [任务大厅](http://127.0.0.1:8030/tasks)
- [性能采样](http://127.0.0.1:8030/performance)

## 6.4 一个“新用户首次上手”的示例流程

这是我更推荐的新用户顺序。

### 示例目标

“我想跑一次 Android 客户端冷启动稳定性检查，看看有没有失败和性能异常。”

### 推荐步骤

1. 先启动 Web，确认平台里已经有什么  

```bash
./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

2. 打开 [首页](http://127.0.0.1:8030/) 看整体状态  
3. 打开 [任务大厅](http://127.0.0.1:8030/tasks) 看有没有现成任务  
4. 如果没有，再用 CLI 创建任务和 Run  
5. 执行 Run  
6. 回到 `/tasks` 看 Run 状态  
7. 到 `/performance` 看是否采到了监控样本  
8. 到 `/issues` 看有没有聚合问题  
9. 如果这次执行与准入相关，再到 `/admission` 看质量门禁和 AdmissionCase  

## 7. 用户下发给 Codex 时，应该怎么描述需求

如果你希望 Codex 帮你操作平台，建议用“目标 + 约束 + 输入 + 输出期望”的方式描述。

下面给你 5 条比较高质量的模板。

### 7.1 创建任务

```text
请在当前 Android Stability Lab 仓库里，帮我创建一个 cold_start_loop 任务：
- 任务名：首页冷启动回归
- 包名：com.example.app
- 设备：emulator-5554
- 采样指标：cpu、memory
- 采样间隔：5 秒
- task_params：{"loop_count": 10}
创建后告诉我 task_id，并说明下一步怎么创建 run。
```

### 7.2 查询结果

```text
请帮我查看 run_id=<run_id> 的执行结果：
- 重点告诉我运行状态
- 有没有失败实例
- 有哪些关键 issue
- 有没有监控样本和 trace
- 给我最值得先看的页面或命令
```

### 7.3 排查失败

```text
请帮我排查最近一次失败 Run：
- 先找最近失败的 run
- 看失败原因属于设备问题、启动问题还是执行问题
- 帮我总结最关键的证据路径
- 如果需要，再告诉我应该去 tasks、performance 还是 issues 页面继续看
```

### 7.4 查看质量门禁

```text
请帮我查看 baseline_key=<baseline_key> 的准入情况：
- 自动结论是什么
- 最终结论是什么
- 有没有人工覆盖
- Top Issue 和性能风险各是什么
- 给我一个适合发给质量负责人看的简短总结
```

### 7.5 通知 / 集成触发

```text
请帮我检查当前 integration outbox 和 CI 回传链路：
- 看有没有 pending / retry / dead_letter 事件
- 如果有 dead-letter，先告诉我风险，再决定是否 replay
- 如果 CI callback 已注册，帮我说明当前 worker 应该怎么跑
```

## 8. 常见问题

### 8.1 我该从哪里开始？

最简单的起点是：

1. 先启动 Web  
2. 看首页 `/`  
3. 看任务大厅 `/tasks`  
4. 再决定是否创建新任务  

如果你已经知道自己要跑什么，再直接用 CLI。

### 8.2 我需要准备什么输入？

最基本的输入通常是：

- Android 包名：`package_name`
- 目标设备：`device_id`
- 任务模板：`template_type`

常见可选输入：

- 任务名 `task_name`
- 采样指标 `metric`
- 采样间隔 `sampling_interval`
- 模板参数 `task_params`
- 运行附加信息 `metadata`

### 8.3 结果在哪里看？

不同结果看不同入口：

- 任务 / Run：`/tasks` 或 `show-run`
- 性能采样：`/performance`
- 问题聚合：`/issues`
- 巡检 / runner：`/runner`
- 准入 / 质量门禁：`/admission`
- JSON / 自动化：`/json-api` 和 `/api/*`

### 8.4 失败了怎么办？

建议先按这个顺序排查：

1. 看设备是否在线：`adb devices`、`list-devices --sync`
2. 看 Run 状态：`show-run --run-id <run_id>`
3. 看任务大厅 `/tasks`
4. 看问题中心 `/issues`
5. 如果和巡检有关，再看 `/runner`
6. 如果和性能样本有关，再看 `/performance`

### 8.5 哪些字段必须填，哪些可选？

以 `create-task` 为例，当前最关键的是：

必须填：

- `--task-name`
- `--package-name`

通常强烈建议填：

- `--template-type`
- `--device`

常见可选：

- `--sampling-interval`
- `--metric`
- `--task-params`
- `--note`
- `--metadata`

### 8.6 我只想看结果，不想研究命令怎么办？

那就这样做：

1. 启动 Web  
2. 打开 `/tasks` 找最近 Run  
3. 打开 `/performance` 看采样  
4. 打开 `/issues` 看问题  
5. 如果需要放行判断，再看 `/admission`

## 9. 当前限制与注意事项

这部分很重要，建议第一次使用前先看。

### 9.1 当前更适合本地部署、本机查看

根据当前代码与文档：

- 当前平台更适合本地部署
- 默认是“自己看自己的本地数据”
- 如果要给别人看，更推荐导出报告、JSON 和产物
- 规则文件也按本地管理理解；需要共享规则结论时，优先导出规则快照、准入评审报告和审计产物

不建议把当前 Web 直接理解成“面向多人在线使用的正式平台”。

### 9.2 Web、CLI、API 能力并不完全一致

当前差异大致如下：

- Web：最适合查看和人工判断
- CLI：最适合创建任务、执行任务、自动化与精确查询
- API：最适合脚本和系统读取

所以不要指望“任何事情在三个入口都同样好用”。

规则治理尤其需要注意：Web 当前更适合查看和预览，CLI 更适合对本地规则文件执行校验、导出、diff、回放和评审；规则源文件仍按本地部署管理，跨团队共享优先使用导出产物和评审报告。

### 9.3 身份与协作能力是本地边界，不是企业统一身份系统

根据当前代码：

- 写操作已经有本地 session / actor 解析和审计
- 写操作也可以消费受信 SSO header：`X-ASL-SSO-Provider`、`X-ASL-External-Subject`、`X-ASL-External-Email`、`X-ASL-Org`、`X-ASL-Team`、`X-ASL-Role`
- `/platform` 和 `/api/platform` 会展示当前身份能力，例如 `local_session` 与 `trusted_sso_header`
- `/api/users` 会提供只读用户目录视图，优先来自服务层 user profile，必要时回退本地 actor
- `/api/responsibility` 会提供只读责任检索视图，汇总 issue、admission、defect、release 等对象上的责任字段
- 但这仍只是正式在线身份边界的最小接入形态，不等于完整企业 SSO 或组织级权限系统

因此：

- 可以把它当成本地操作留痕
- 可以在可信反向代理/网关注入并清洗 header 后，把它用于写操作身份和审计
- 可以把 `/api/users` 和 `/api/responsibility` 当作责任检索和审计增强入口
- 不建议把它当作完整权限平台来依赖
- 不建议把它理解成已经完成真正跨系统责任自动同步

### 9.4 集成能力已经能用，但仍偏本地运营面

outbox / webhook / worker / replay 已经存在，但当前更像：

- 本地可运营
- 本地可回放
- 本地可观察

而不是“已经天然适合复杂生产网络拓扑的中心化集成平台”。

### 9.5 仍缺少一些对用户更友好的说明信息

根据当前仓库，我认为还缺这些内容，后续建议补齐：

- 一个更明确的“任务模板字段说明”
- 一个“常见 task_params 示例库”
- 一个“典型失败案例排查图”
- 一个“结果产物目录说明”
- 一个“非技术用户只看 Web 的上手页”

## 10. 给非技术用户的最短版使用说明

这部分可以直接拿去给第一次接触平台的人。

1. 先启动平台页面：`./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030`
2. 打开首页：`http://127.0.0.1:8030/`
3. 想看任务和执行结果，就进“任务大厅”
4. 想看性能采样有没有采到，就进“性能采样”
5. 想看最近常见问题，就进“问题中心”
6. 想看无人值守和日报周报，就进“巡检状态”
7. 想看准入结论和人工确认，就进“准入中心”
8. 没有现成任务时，用 CLI 先 `create-task -> create-run -> execute-run`
9. 结果看不懂时，优先把 `run_id`、页面链接和关键报错发给 Codex
10. 这是本地优先平台，默认更适合本机查看和导出结果共享

## 11. 给平台使用方的建议

如果你只是普通使用者，我建议你记住下面这条最短主线：

**先看首页，再看任务大厅；要看采样去性能页；要看问题去问题中心；要做放行判断去准入中心；要做自动化或批量执行再用 CLI。**

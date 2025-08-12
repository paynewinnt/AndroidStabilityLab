# Android Stability Lab V2验收清单

本文档面向 `V2` 版本验收，目标是把“当前 `V2` 已完成到什么程度”和“应该如何逐项验收”统一到同一份清单里。

## 1. 完成度判断

整体判断：**`V2 Must` 已基本完成，`Should` 大部分完成，仍有少量 `P1/P2` 缺口不建议再混入 `V2 Must` 阻塞项。**

当前判断依据：

- `V2` 主分析链已经可用：问题聚合、`Top Issue`、版本/设备/场景对比、性能趋势对比、回归判断、分析快照、规则治理、规则回放、golden suite 验收、规则评审报告与基线治理都已有代码和测试覆盖
- 针对 `V2` 主链的核心单测当前可通过：`tests.test_analysis_service / test_comparison_service / test_performance_trend_service / test_regression_service / test_snapshot_service / test_attribution_service / test_rule_review_service / test_rule_review_report_service / test_cli_task_create`
- `V2` 文档里提到的若干增强项仍未完整落地，例如：
  - 人工合并/拆分问题、误报忽略等分析治理动作
  - `perfetto` 扩展证据接入
  - 高级异常识别的截图、SurfaceFlinger、帧刷新、输入事件等多证据交叉确认
  - 性能风险阈值从外部规则文件或页面治理入口加载，并基于真实样本标定
  - 更正式的问题中心页面和“问题详情中的趋势联动”可视化消费层

因此本清单采用两层口径：

- `Must`：作为 `V2` 是否达到“分析闭环可验收”的硬门槛
- `建议补验项`：作为 `V2` 增强能力或后续收尾项，不作为当前版本阻塞条件

## 2. 入口

当前仓库**还没有单独的 `verify_v2_acceptance.sh` 一键脚本**，建议用下面两类入口组合验收。

### 2.1 默认安全回归入口

```bash
./.venv/bin/python -m unittest \
  tests.test_analysis_service \
  tests.test_comparison_service \
  tests.test_performance_trend_service \
  tests.test_regression_service \
  tests.test_snapshot_service \
  tests.test_attribution_service \
  tests.test_rule_review_service \
  tests.test_rule_review_report_service \
  tests.test_cli_task_create
```

### 2.2 语法与装配检查

```bash
python -m py_compile stability/cli/task_create.py
python -m py_compile stability/app/analysis_service.py
python -m py_compile stability/app/comparison_service.py
python -m py_compile stability/app/performance_trend_service.py
python -m py_compile stability/app/regression_service.py
python -m py_compile stability/app/snapshot_service.py
python -m py_compile stability/app/attribution_service.py
python -m py_compile stability/app/rule_review_service.py
python -m py_compile stability/app/rule_review_report_service.py
```

## 3. 前置条件

- `./.venv/bin/python` 或 `python3` 可用
- 若要验证真实数据链路，持久化库中至少已有一批 `task/run/instance/issue/report` 数据
- 若要验证性能趋势与回归，对比两侧需要已有可用监控 session
- 若要验证规则回放与规则评审，仓库内默认配置文件需存在：
  - [config/stability_rules.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/stability_rules.json)
  - [config/rule_review_policy.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/rule_review_policy.json)
  - [config/rule_review_baseline_policy.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/rule_review_baseline_policy.json)
  - [config/rule_replay_golden_samples.json](/Users/ryan.rr.penn/Develop/projects/python/AndroidStabilityLab/config/rule_replay_golden_samples.json)

## 4. Must 验收项

以下项目应全部通过，`V2` 才视为达到“分析闭环可验收”状态。

### 4.1 本地基线

- 上述 `V2` 目标单测全部通过
- 核心分析与治理 CLI 帮助命令可用：
  - `list-top-issues`
  - `show-issue-group`
  - `compare-issues`
  - `compare-performance-trends`
  - `judge-regression`
  - `create-analysis-snapshot`
  - `show/validate/export/diff-analysis-rules`
  - `replay/review-analysis-rules`
  - `verify/list/show/diff/draft/promote-rule-replay-golden-*`
  - `create/compare/set/show/promote/rollback/list/create/show-rule-review-report-*`
  - `delete-analysis-snapshot`
  - `prune-analysis-snapshots`

建议检查命令：

```bash
./.venv/bin/python -m stability.cli --help
./.venv/bin/python -m stability.cli list-top-issues --help
./.venv/bin/python -m stability.cli compare-issues --help
./.venv/bin/python -m stability.cli compare-performance-trends --help
./.venv/bin/python -m stability.cli judge-regression --help
./.venv/bin/python -m stability.cli create-analysis-snapshot --help
./.venv/bin/python -m stability.cli review-analysis-rules --help
./.venv/bin/python -m stability.cli create-rule-review-report --help
```

### 4.2 问题聚合与 Top Issue

- 能从多次执行结果中聚合同类问题
- `list-top-issues` 可按 `task_id / status / template_type / version / package_name / device_id / issue_type / created_from / created_to` 输出稳定结果
- `show-issue-group` 可从聚合问题下钻到样本事件、报告路径、执行日志路径和证据路径
- 聚合结果在重复计算中口径稳定

建议检查命令：

```bash
./.venv/bin/python -m stability.cli list-top-issues --package-name com.example.app
./.venv/bin/python -m stability.cli show-issue-group --fingerprint IFP
```

通过标准：

- 输出为合法 JSON
- 任一聚合问题都可追溯到原始异常事件或样本事件
- `show-issue-group` 返回中包含样本事件、报告引用和归因结果或归因缺省说明

### 4.3 多维对比

- 能完成版本维度对比
- 能完成设备维度对比
- 能完成场景维度对比
- 对比结果能输出样本说明、问题变化摘要和不可比提示

建议检查命令：

```bash
./.venv/bin/python -m stability.cli compare-issues --dimension version --left-value 1.0.0(100) --right-value 2.0.0(200)
./.venv/bin/python -m stability.cli compare-issues --dimension device --left-value DEVICE_A --right-value DEVICE_B
./.venv/bin/python -m stability.cli compare-issues --dimension scenario --left-value monkey --right-value cold_start_loop
```

通过标准：

- 三个核心维度至少都能返回结构化结果
- 差异结果至少包含 `added / removed / changed / unchanged` 或等价摘要
- 不可比场景会显式给出说明，而不是静默返回空结论

### 4.4 性能趋势与回归判断

- 能比较 `CPU / memory PSS / FPS / power` 等关键指标
- 能输出 issue 级与 metric 级回归判断
- 自动结论至少覆盖：
  - `obvious_regression`
  - `suspected_regression`
  - `no_obvious_change`
  - `insufficient_data`
- 关键指标变化可进入整体回归判断，而不是只做展示

建议检查命令：

```bash
./.venv/bin/python -m stability.cli compare-performance-trends --dimension version --left-value 1.0.0(100) --right-value 2.0.0(200)
./.venv/bin/python -m stability.cli judge-regression --dimension version --left-value 1.0.0(100) --right-value 2.0.0(200)
```

通过标准：

- 性能趋势结果同时提供平均值、峰值、`P95` 和最新值
- 指标结果至少覆盖 `worsened / unchanged / improved / insufficient_data`
- 任一回归结论都可回溯到比较范围、阈值来源和规则版本

### 4.5 分析快照

- 可固化以下类型快照：
  - `top_issues`
  - `comparison`
  - `regression`
  - `replay`
  - `review`
- 快照创建后可再次查看，不依赖实时重算
- 快照能保留数据范围、筛选条件、规则版本和关键结论
- 快照能保留 `source_refs` 和基础完整性检查结果

建议检查命令：

```bash
./.venv/bin/python -m stability.cli create-analysis-snapshot --snapshot-type top_issues --name "Top Issues Snapshot"
./.venv/bin/python -m stability.cli create-analysis-snapshot --snapshot-type comparison --name "Comparison Snapshot" --dimension version --left-value 1.0.0(100) --right-value 2.0.0(200)
./.venv/bin/python -m stability.cli create-analysis-snapshot --snapshot-type regression --name "Regression Snapshot" --dimension version --left-value 1.0.0(100) --right-value 2.0.0(200)
./.venv/bin/python -m stability.cli list-analysis-snapshots
./.venv/bin/python -m stability.cli show-analysis-snapshot --snapshot-id SNAPSHOT_ID
```

通过标准：

- 快照可落盘到 `runtime/analysis_snapshots/`
- `show-analysis-snapshot` 可返回 `summary / payload / source_refs / integrity`
- 快照内容与创建时的核心结论一致

### 4.6 规则治理、规则回放与 golden suite

- 可查看、校验、导出和 diff 当前分析规则
- 可通过更正式入口只读查看规则来源、默认规则、生效规则，并对候选规则做编辑预览；预览结果应继续引导校验、diff、回放和评审，而不是直接保存线上规则
- 可用同一批历史样本回放基线/候选规则
- 可运行仓库内置 golden suite 验收集
- 可查看正式 golden suite 清单、单 case 详情和双 suite diff
- 可从真实 run 生成 golden draft，并受控提升进正式 golden suite

建议检查命令：

```bash
./.venv/bin/python -m stability.cli show-analysis-rules
./.venv/bin/python -m stability.cli validate-analysis-rules
./.venv/bin/python -m stability.cli export-analysis-rules --output /tmp/effective_rules.json --overwrite
./.venv/bin/python -m stability.cli diff-analysis-rules --left-view effective --right-view source
./.venv/bin/python -m stability.cli replay-analysis-rules --candidate-path config/stability_rules.json
./.venv/bin/python -m stability.cli verify-rule-replay-golden-samples
./.venv/bin/python -m stability.cli list-rule-replay-golden-samples
```

通过标准：

- 规则治理链路可稳定返回结构化结果
- 规则配置入口按只读配置中心和候选编辑预览验收；规则文件仍由本地配置管理，导出快照/评审报告/JSON 产物仍是共享口径
- golden suite 验收可返回通过/失败、层级汇总和 case 明细
- 规则回放结果能清晰区分 `regrouped / fingerprint_changed / count_changed / added / removed`

### 4.7 规则评审、评审报告与基线治理

- `review-analysis-rules` 可输出 `pass / conditional_pass / fail`
- 规则评审结果可固化成 `review` 快照
- 多条 `review` 快照可汇总成评审报告
- 两份评审报告可做 delta 对比
- 已落盘评审报告可注册命名基线、晋升、回滚，并生成 latest 审计

建议检查命令：

```bash
./.venv/bin/python -m stability.cli review-analysis-rules --candidate-path config/stability_rules.json
./.venv/bin/python -m stability.cli create-rule-review-report --name "Review Report"
./.venv/bin/python -m stability.cli compare-rule-review-reports --name "Review Compare" --left-report-id LEFT --right-report-id RIGHT
./.venv/bin/python -m stability.cli set-rule-review-report-baseline --baseline-key default --report-id REPORT_ID
./.venv/bin/python -m stability.cli show-rule-review-report-baseline --baseline-key default
./.venv/bin/python -m stability.cli show-rule-review-report-baseline-audit --baseline-key default
```

通过标准：

- 评审结论同时带规则命中、样本变化和 golden suite 结果
- 评审报告能输出 `JSON / Markdown / HTML`
- 基线历史、latest audit 和版本索引可追溯到 `who / when / from / to / why`

### 4.8 规则式初步归因、高级异常初步识别与扩展证据

- `show-issue-group` 可给出规则式初步归因、命中依据、置信度和规则版本
- 当前归因可消费 issue title、summary、process、artifact path、metadata / evidence 等样本信号，形成最小 evidence-aware 解释
- 黑屏/freeze/system_server crash/watchdog 当前按文本启发式形成初步 issue，并保留结构化 evidence 与命中片段供人工复核
- OOM、内存上涨、卡顿/帧耗时恶化当前以启发式阈值输出结构化 `performance_risk_items`
- 性能风险主链已支持配置对象注入和按设备、包名、场景等 scoped override，并可输出阈值来源、命中 scope 与阈值值；但外部规则文件/页面治理入口加载和真实阈值标定不作为当前 `V2 Must` 硬门槛
- 当前首批扩展证据链路可覆盖：
  - `dropbox`
  - `dumpsys meminfo`
  - `dumpsys SurfaceFlinger`
- 归因与证据引用不会破坏主体分析链
- 以上能力应按“初步识别/启发式风险/规则式初步归因建议”验收，不按完整智能诊断、AI 根因诊断或自动根因判断验收

通过标准：

- 首批高频问题类型能输出初步归因，并能展示方向、命中规则、命中字段、证据片段、置信度和规则版本
- 黑屏/freeze/system_server crash/watchdog 命中结果能追溯到结构化 evidence 与文本证据片段
- 性能风险项能说明指标、观测值、阈值来源、命中 scope 和阈值值
- 分析人员可从问题样本追溯到扩展证据路径
- 某类证据缺失时，主体 issue、聚合和快照链路仍可正常工作

## 5. 数据验收项

以下项目应在抽样检查中成立：

- 任一聚合问题都可追溯到原始异常事件
- 任一回归结论都可追溯到比较范围和规则版本
- 任一快照都可追溯到创建时间、筛选条件和数据范围
- 任一规则评审报告都可追溯到来源 `review` 快照
- 任一 latest audit 都可追溯到对应 revision 历史

## 6. 建议补验项

以下项目建议继续跟踪，但**不建议作为当前 `V2 Must` 阻塞条件**：

- 人工合并/拆分问题、误报忽略、手工调整标题/严重级别
- `perfetto` 扩展证据接入与异步解析
- 截图、SurfaceFlinger、帧刷新、输入事件等多证据交叉确认
- 性能风险阈值外部规则文件/页面治理入口加载与真实样本标定
- 在线保存、发布、审批和回滚规则的完整编辑器能力；当前只读配置中心与编辑预览不应阻塞 `V2 Must`
- 更正式的问题中心页面与问题详情趋势联动视图
- 更复杂的排序策略和更细粒度的性能退化统计

## 7. 当前不建议计入 V2 阻塞的项

以下内容虽然在更大产品路线里有价值，但不应再混入 `V2` 阻塞范围：

- 团队协作流转
- 准入流程编排与完整评审闭环
- Web 主入口作为正式团队平台
- 复杂权限体系
- 深度外部系统集成

这些已经属于 `V3` 或 `V2` 之后的增强域。

## 8. 通过结论

满足以下条件时，可判定 `V2` 达到可验收状态：

- `Must` 验收项全部通过
- 至少保留一组最新的 `V2` 目标测试通过记录
- 关键 CLI 与快照/规则治理链路能在当前仓库中独立复现
- 当前已知剩余问题不影响“聚合 -> 对比 -> 回归 -> 快照 -> 规则治理”这条分析闭环可信度

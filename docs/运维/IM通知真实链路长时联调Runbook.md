# IM 通知真实链路长时联调 Runbook

## 1. 链路选择

本轮 P0 外部集成真实链路建议优先选择 **IM 通知链路** 做长时联调，而不是同时压上 CI、缺陷和提测平台。

当前 IM 链路分两类出口：

- `im_notify`：ASL 通用 IM 合同，适合接自建接收器或企业内部适配器，body 为 `asl.im_notify.v1`，签名在 `X-ASL-Signature` header。
- `feishu_bot`：飞书自定义机器人出口，适合直接接飞书群机器人，body 为飞书机器人格式，包含 `timestamp / sign / msg_type / content`，签名按飞书规则生成。

选择原因：

- 代码已有专用入口：`register-im-webhook`、`run-im-notify-worker`、`im_notify` delivery channel。
- 飞书机器人已有专用入口：`register-feishu-webhook`、`run-feishu-notify-worker`、`feishu_bot` delivery channel。
- 消息合同已固定为 `asl.im_notify.v1`，事件覆盖协作事件、准入结论和 `outbox.retry_alert`。
- IM 机器人或企业 IM inbound webhook 更容易拿到真实 endpoint，便于先验证签名、幂等、receipt、重试和噪声治理。
- CI 链路已有 `sync-ci-admission-decisions` 和 `run-ci-admission-sync-worker`，但通常需要流水线权限、门禁策略和回调字段进一步对齐，适合作为第二条真实链路。

本 runbook 的目标是先用本地 mock/smoke 验证出站链路、合同、worker、receipt 和重试观测面，再把同一套配置切换到真实 IM/飞书 endpoint 完成 2 小时试运行和 24 小时长时联调，并形成可复制的外部集成运营基线。

验收路径分三段：

- 本地 mock/smoke：只验证平台侧 IM delivery channel、`asl.im_notify.v1` payload、签名 header 生成、worker 运行、receipt 持久化、dead-letter/replay 观测和 Web/API 运维面。它不证明真实 IM 机器人、企业网关、群消息格式、真实限流或噪声治理已经通过。
- 真实 2 小时试运行：使用真实 IM/飞书 endpoint 验证 `FEISHU_WEBHOOK_URL / FEISHU_SIGNING_SECRET`、worker 命令、飞书群可达性、验签、consumer receipt、限流和噪声反馈；它只作为进入 24 小时联调的准入。
- 真实 24 小时联调：使用真实 IM inbound webhook 和真实接收方验签/幂等逻辑，连续运行至少 24 小时，验证 endpoint 可用性、验签、幂等、consumer receipt、失败分级、replay、限流和通知噪声。

## 2. 准备项

本地 mock/smoke 前确认：

- `.venv` 已安装项目依赖，或系统中可用 `python3`。
- 本地持久化目录可写，默认 outbox 数据在 `runtime/integration_outbox/`。
- 已有或可以通过正常协作/准入写操作生成至少一条 `admission_case.updated`、`admission.override_recorded` 或 `outbox.retry_alert` pending 事件。若没有 pending 事件，worker 只能验证注册、启动和空队列退出，不能验证投递 payload。

真实 2 小时试运行和 24 小时联调前确认：

- 已有真实 IM inbound webhook URL，非本地地址必须是 `https`。
- 如果接自建 IM 适配器，已准备 ASL `signing_secret`，接收端按 `X-ASL-Signature` 做 HMAC-SHA256 校验。
- 如果直接接飞书自定义机器人，已准备飞书机器人签名密钥，平台会按飞书规则在 body 中生成 `timestamp / sign`；不要把这类密钥提交到仓库。
- 已确定 webhook 名称，例如 `prod-im-notify`。
- 已确认本地持久化目录可写，默认 outbox 数据在 `runtime/integration_outbox/`。
- 已和接收方约定收到重复 `X-ASL-Idempotency-Key` 时返回 2xx，并以幂等方式忽略重复消息。

## 3. 本地 Mock/Smoke 验证

先跑不依赖外部 endpoint 的单元 smoke：

```bash
./.venv/bin/python -m unittest \
  tests.test_integration_outbox_service \
  tests.test_cli_web_integration_commands \
  -v
```

再启动一个临时本地接收器，用于记录请求头和 body：

```bash
python - <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

log = Path("/tmp/asl-im-smoke-receiver.log")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        log.write_text(
            f"path={self.path}\n"
            f"headers={dict(self.headers)}\n"
            f"body={body.decode('utf-8', errors='replace')}\n",
            encoding="utf-8",
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"consumer_id":"local-im-smoke","receipt_id":"local-receipt-1"}')

HTTPServer(("127.0.0.1", 9010), Handler).serve_forever()
PY
```

在另一个终端注册本地 IM webhook。`127.0.0.1` 属于本地 mock，允许使用 `http`；真实 endpoint 仍必须使用 `https + signing_secret`。

```bash
python -m stability.cli register-im-webhook \
  --name local-im-smoke \
  --url http://127.0.0.1:9010/asl/im \
  --event-type admission_case.updated \
  --event-type admission.override_recorded \
  --event-type outbox.retry_alert \
  --created-by smoke
```

执行单轮本地 smoke：

```bash
python -m stability.cli run-im-notify-worker \
  --webhook-name local-im-smoke \
  --limit-per-webhook 5 \
  --max-rounds 1
```

本地 smoke 成功判定：

- 单元 smoke 退出码为 `0`。
- `register-im-webhook` 输出 `delivery_channel=im_notify` 和 `delivery_contract_version=asl.im_notify.v1`。
- 有 pending 事件时，`run-im-notify-worker` 至少 attempted 一条事件，临时接收器日志 `/tmp/asl-im-smoke-receiver.log` 能看到 `X-ASL-Delivery-Contract`、`X-ASL-Callback-Contract-Version`、`X-ASL-Idempotency-Key` 和 JSON body。
- body 中 `contract_version=asl.im_notify.v1`，`delivery_channel=im_notify`，并保留原始 event 信息。
- `/api/integration/outbox` 或 `runtime/integration_outbox/` 中可回看 delivery receipt / consumer receipt / worker status。
- 若无 pending 事件，允许 smoke 只证明注册和 worker 空跑不报错，但不能标记为“投递链路已验收”。

本地 smoke 与真实 2 小时试运行/24 小时联调的差异：

- 本地 smoke 不验证真实 IM 平台限流、机器人消息格式、企业网关鉴权、真实证书链、网络抖动和跨网段访问。
- 本地 smoke 的 `http://127.0.0.1` 只用于开发验收；真实 endpoint 必须是 `https`，且必须配置 `signing_secret`。
- 本地 smoke 可以用临时 receipt 模拟下游确认；真实联调必须由接收方按 `X-ASL-Idempotency-Key` 幂等去重，并返回真实 `consumer_id` / `receipt_id`。
- 本地 smoke 不等价于通知噪声已治理；噪声治理只能在真实 IM 群、真实事件频率和真实值班反馈下验收。

## 4. 注册真实 Webhook

推荐先只订阅低噪声事件，等 2 小时稳定后再扩展。

### 4.1 注册通用 IM Webhook

当下游是自建 IM 适配器或企业内部中转服务时，使用 `register-im-webhook`：

```bash
python -m stability.cli register-im-webhook \
  --name prod-im-notify \
  --url https://im.example.com/asl/inbound \
  --signing-secret "$ASL_IM_SIGNING_SECRET" \
  --signature-key-id v1 \
  --secret-hint "im-prod-v1" \
  --failure-policy retryable_http \
  --event-type admission_case.updated \
  --event-type admission.override_recorded \
  --event-type outbox.retry_alert \
  --created-by ops
```

### 4.2 注册飞书自定义机器人

当下游是飞书群自定义机器人时，使用 `register-feishu-webhook`。它会把 ASL 通知转换为飞书机器人 `text` 消息，并使用飞书签名密钥生成 body 内的 `timestamp / sign`。

```bash
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/<token>"
FEISHU_SIGNING_SECRET="<feishu-bot-secret>"

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
```

飞书接入注意事项：

- `signing_secret` 会写入本地 `runtime/integration_outbox/webhooks.json`，属于本机运行配置；不要提交 `runtime/`。
- 飞书机器人安全设置如启用“关键词”，消息里必须包含对应关键词，否则飞书会拒收。
- 当前飞书通道先使用 `msg_type=text`，用于联通和噪声治理；如需更好的排版，再扩展交互卡片。

如需密钥轮换，可注册时保留上一版 key id：

```bash
python -m stability.cli register-im-webhook \
  --name prod-im-notify-v2 \
  --url https://im.example.com/asl/inbound \
  --signing-secret "$ASL_IM_SIGNING_SECRET_V2" \
  --signature-key-id v2 \
  --accepted-signature-key-id v1 \
  --secret-hint "im-prod-v2" \
  --failure-policy retryable_http \
  --created-by ops
```

## 5. 启动真实 Worker

### 5.1 环境变量

飞书机器人真实联调必须从本机环境变量读取 URL 和签名密钥，不在命令行历史、文档或仓库里写明文：

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/<token>"
export FEISHU_SIGNING_SECRET="<feishu-bot-secret>"
```

约束：

- `FEISHU_WEBHOOK_URL` 只允许使用真实飞书机器人 `https` 地址。
- `FEISHU_SIGNING_SECRET` 对应飞书机器人安全设置里的签名密钥，不等同于 ASL 通用 IM `ASL_IM_SIGNING_SECRET`。
- 注册后密钥会进入本机 `runtime/integration_outbox/webhooks.json`，该目录只作为运行态配置和审计证据，不提交仓库。
- 飞书机器人如开启关键词安全策略，试运行前需确认 ASL 消息文本包含关键词，否则会出现 4xx 拒收。

### 5.2 Worker 命令

单轮冒烟：

```bash
python -m stability.cli run-im-notify-worker \
  --webhook-name prod-im-notify \
  --limit-per-webhook 5 \
  --max-rounds 1
```

飞书机器人对应命令：

```bash
./.venv/bin/python -m stability.cli run-feishu-notify-worker \
  --webhook-name "Android Stability Lab" \
  --limit-per-webhook 5 \
  --max-rounds 1 \
  --stop-when-idle
```

2 小时试运行用于验证真实飞书群可达性、签名、receipt、限流和噪声，不等于 24 小时验收通过：

```bash
python -m stability.cli run-im-notify-worker \
  --daemon \
  --webhook-name prod-im-notify \
  --interval-seconds 60 \
  --limit-per-webhook 20 \
  --max-runtime-seconds 7200
```

飞书机器人 2 小时试运行：

```bash
./.venv/bin/python -m stability.cli run-feishu-notify-worker \
  --daemon \
  --webhook-name "Android Stability Lab" \
  --interval-seconds 60 \
  --limit-per-webhook 20 \
  --max-runtime-seconds 7200
```

24 小时长时联调用于最终验收真实 endpoint 的长时稳定性：

```bash
python -m stability.cli run-im-notify-worker \
  --daemon \
  --webhook-name prod-im-notify \
  --interval-seconds 300 \
  --limit-per-webhook 50 \
  --max-runtime-seconds 86400
```

飞书机器人 24 小时长时联调：

```bash
./.venv/bin/python -m stability.cli run-feishu-notify-worker \
  --daemon \
  --webhook-name "Android Stability Lab" \
  --interval-seconds 300 \
  --limit-per-webhook 50 \
  --max-runtime-seconds 86400
```

后台托管由部署环境负责，例如 systemd、supervisor、launchd 或 CI runner 常驻任务。当前 CLI daemon 会在进程内循环并写入 `worker_status.json`，不是完整进程守护器。

### 5.3 2 小时试运行检查点

2 小时试运行期间每 30 分钟记录一次：

- worker 进程是否仍在运行，或是否按 `max-runtime-seconds=7200` 正常退出。
- `/api/integration/outbox` 中 `worker_status.run_count` 是否增长，`last_error` 是否为空。
- `attempt_count / delivered_count / failed_count / dead_lettered_count / remaining_pending_count` 是否异常增长。
- 飞书群是否收到预期事件，是否存在关键词拦截、机器人限流、消息格式异常或刷屏。
- `consumer_receipts` 是否包含飞书侧返回的确认信息，至少能关联到 `event_id / webhook_name / idempotency_key`。

2 小时试运行结论只能写为：

- `通过，可进入 24 小时联调`：无 dead-letter、无连续失败、消息可读且值班反馈可接受。
- `条件通过，需修复后再跑 24 小时`：存在偶发失败或噪声问题，但根因明确且已记录修复动作。
- `不通过`：worker 异常退出、签名/关键词/限流导致不可用、dead-letter 未闭环、或飞书群反馈不可接受。

## 6. 签名、幂等和 Receipt

发送端固定写入以下关键 header：

- `X-ASL-Event-Id`：outbox event id。
- `X-ASL-Event-Type`：事件类型。
- `X-ASL-Delivery-Attempt`：当前投递尝试次数。
- `X-ASL-Idempotency-Key`：按事件类型、目标对象和 payload 派生的稳定幂等键。
- `X-ASL-Signature`：有 `signing_secret` 时为 `sha256=<hmac>`。
- `X-ASL-Signature-Alg`：有密钥时为 `hmac-sha256`。
- `X-ASL-Signature-Key-Id`：当前密钥版本。
- `X-ASL-Delivery-Contract`：`asl.webhook_delivery.v1`。
- `X-ASL-Callback-Contract-Version`：`asl.webhook_callback.v1`。
- `X-ASL-Failure-Policy`：当前失败策略。

接收端要求：

- 用原始 request body 和共享密钥校验 `X-ASL-Signature`。
- 以 `X-ASL-Idempotency-Key` 做去重，重复消息返回 2xx。
- 成功时返回 2xx；响应体可包含 `consumer_id`、`receiver`、`receipt_id` 或 `consumer_receipt_id`，平台会沉淀为 `consumer_receipts`。
- 对业务不可处理但不应重试的请求返回 4xx；对限流、锁冲突、临时不可用返回 408、409、425、429 或 5xx。

平台侧观测：

- 成功投递会把事件置为 `delivered`，并记录 `consumer_receipts`、`delivered_at`、`last_response_code`。
- 已有同 webhook、同 idempotency key 的 consumer receipt 时，后续轮次会 `deduplicated_count + 1` 并跳过重复投递。
- `/api/integration/outbox` 可查看 worker status、delivery receipt、consumer receipt、幂等键和 replay 状态。

## 7. 失败分级

当前失败分类按 HTTP/传输层归因：

- `transport_error`：网络、DNS、TLS、连接超时或接收端不可达。
- `server_error`：HTTP 5xx。
- `retryable_client_error`：408、409、425、429。
- `client_error`：其他非重试 4xx。
- `*:dead_letter`：达到死信阈值或不可重试失败后的终态。

处理建议：

- `transport_error`、`server_error`、`retryable_client_error` 先看接收端可用性、限流和证书，等待 backoff 或人工 replay。
- `client_error` 优先检查 URL、签名密钥、事件订阅、body 字段和接收端 schema，不要直接 replay。
- `outbox.retry_alert` 进入 IM 时，应由值班人确认原事件是否需要修复配置、重放或暂停链路。

## 8. Dead-letter Replay

先预览：

```bash
python -m stability.cli replay-integration-dead-letters \
  --event-type admission_case.updated \
  --limit 20
```

确认根因已修复后执行：

```bash
python -m stability.cli replay-integration-dead-letters \
  --event-type admission_case.updated \
  --limit 20 \
  --replayed-by ops \
  --execute
```

执行后平台会：

- 将匹配的 `dead_letter` 事件重新排回 `pending`。
- 清理 `last_error / last_response_code / dead_lettered_at`。
- 写入 replay receipt 和 operator receipt。
- 下一轮 worker 继续按原 webhook 订阅和幂等键投递。

Replay 前必须确认接收端仍按同一 `X-ASL-Idempotency-Key` 幂等处理，避免重复通知或重复外部动作。

Replay 验收记录必须包含：

- replay 前的 `event_id / event_type / webhook_name / delivery_status / failure_category / last_error`。
- replay 触发人、触发时间、修复动作和是否执行 `--execute`。
- replay 后事件是否重新进入 `pending`，下一轮 worker 是否转为 `delivered`。
- replay 后是否产生新的 `delivery_receipt / consumer_receipt / operator receipt`。
- 飞书群是否出现重复业务动作；若重复出现，必须把根因归为幂等缺陷，不能标记 replay 通过。

## 8.1 Receipt 反查

联调期间至少抽查 3 条真实消息做 receipt 反查，覆盖正常消息、重复幂等消息和 replay 后消息。

推荐反查路径：

```bash
./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

然后访问：

- `http://127.0.0.1:8030/api/integration/outbox`

反查字段：

- `event_id`：必须能对应飞书群里看到的消息或接收端日志。
- `event_type`：必须属于本次订阅范围。
- `webhook_name`：通用 IM 为 `prod-im-notify` 或实际名称；飞书为 `Android Stability Lab` 或实际名称。
- `delivery_status`：成功消息应为 `delivered`。
- `last_response_code`：成功消息应为 2xx。
- `idempotency_key`：接收端日志和平台侧必须一致。
- `delivery_receipt`：必须能看到投递尝试、响应码和时间。
- `consumer_receipt`：真实联调必须由下游响应提供，不能只依赖 transport ack。
- `replay_receipt / operator_receipt`：仅 replay 场景必填，用于证明谁在何时重放了什么。

验收记录中不要粘贴密钥、完整 webhook token 或敏感 payload；可保留 `event_id`、脱敏 URL、响应码、receipt id 和截图/日志路径。

## 9. 订阅和噪声治理

首轮真实链路只建议订阅：

- `admission_case.updated`
- `admission.override_recorded`
- `outbox.retry_alert`

稳定后再按需增加：

- `issue.assigned`
- `issue.transitioned`
- `issue.commented`
- `admission_case.assigned`
- `admission_case.commented`
- `admission_case.transitioned`

噪声治理原则：

- 默认按结果类、告警类事件接入，不默认打开所有评论类事件。
- 同一个 IM 群只承接一个环境或一个产品线，避免 dev/staging/prod 混发。
- 对 `commented` 类事件先做小群试点，确认不会形成刷屏后再扩展。
- `outbox.retry_alert` 必须保留，但需要值班人闭环，不应作为普通提醒长期忽略。
- 如果需要按应用、版本、责任组订阅，当前先通过注册多个 webhook 和不同 `--event-type` 组合拆分；完整订阅管理 UI/规则仍属后续治理。

## 10. 长时联调验收指标

本地 smoke 通过后，只能进入真实 2 小时试运行准入，不代表真实链路已完成。真实 24 小时联调通过标准：

- worker 无异常退出，`worker_status.status` 最终为 `idle` 或托管进程仍在运行。
- `last_error` 为空，`run_count` 持续增长。
- 真实 IM 接收端收到消息，且消息体 `contract_version=asl.im_notify.v1`。
- 接收端验签通过率 100%。
- 接收端以 `X-ASL-Idempotency-Key` 去重，人工重复投递不产生重复业务动作。
- 成功事件均有 `consumer_receipts`，响应码为 2xx。
- `dead_lettered_count=0`；如发生 dead-letter，必须有原因、修复记录、replay receipt 和 operator receipt。
- `remaining_pending_count` 不持续增长；如增长，需要能解释为接收端限流、暂停或事件突增。
- 通知噪声可接受，核心群无大量无行动价值消息。

建议记录每次联调的开始时间、结束时间、webhook 名称、订阅事件、worker 参数、总投递量、失败量、dead-letter 数、replay 次数、接收端验签结果和噪声反馈。

建议量化指标：

- 运行时长：2 小时试运行必须达到 `>= 120` 分钟；24 小时联调必须达到 `>= 24` 小时，且中断累计不超过 10 分钟并有记录。
- 投递成功率：真实可投递事件按 `delivered / attempted >= 99%`；若样本量小于 20 条，必须逐条列出事件和 receipt。
- 验签通过率：100%，任何验签失败都必须先修复后重新计时。
- 幂等重复率：人工重复投递或 replay 不产生重复外部业务动作，重复消息必须被接收端 2xx 幂等确认。
- Dead-letter：最终通过时必须为 0；若试运行期间发生过 dead-letter，必须完成根因、修复、replay 和 receipt 反查。
- 噪声反馈：值班人明确选择 `可接受`；若为 `偏高` 或 `不可接受`，不能直接进入最终通过。

最终通过标准：

- `平台侧能力通过` 只能说明 register/worker/outbox/replay/receipt 机制可用。
- `2 小时试运行通过` 只能说明真实飞书 endpoint 可以进入长时联调。
- `24 小时真实联调通过` 必须同时满足运行时长、验签、幂等、receipt、dead-letter、replay、噪声反馈和回滚预案全部条件。
- 未跑满 24 小时，或 24 小时内关键缺陷未闭环，只能写为 `条件通过` 或 `不通过`，不能写成 `IM 真实链路完成`。

## 10.1 验收记录模板

可直接复制到 `docs/运维/飞书IM真实链路2小时与24小时验收记录-YYYY-MM-DD.md`：

```markdown
# 飞书 IM 真实链路 2 小时与 24 小时验收记录 - YYYY-MM-DD

## 基本信息

- Webhook 名称：
- URL 脱敏：
- 环境变量：`FEISHU_WEBHOOK_URL` 已配置 / `FEISHU_SIGNING_SECRET` 已配置
- 订阅事件：
- Worker 命令：
- 执行人：
- 值班/反馈人：
- 开始时间：
- 结束时间：
- 实际运行时长：

## 2 小时试运行

- 结论：`通过，可进入 24 小时联调 / 条件通过 / 不通过`
- attempted：
- delivered：
- failed：
- dead_lettered：
- remaining_pending：
- worker_status：
- 飞书群收到消息：`是 / 否`
- 飞书签名通过率：
- 关键词/限流/格式问题：
- 噪声反馈：`可接受 / 偏高 / 不可接受`
- 样本 receipt 反查：
- 问题和处理：

## 24 小时联调

- 结论：`通过 / 条件通过 / 不通过`
- attempted：
- delivered：
- failed：
- dead_lettered：
- replay 次数：
- remaining_pending 趋势：
- worker 异常退出：
- 飞书签名通过率：
- 幂等重复投递验证：
- consumer receipt 抽查：
- dead-letter replay 抽查：
- 噪声反馈：
- 暂停/回滚演练或预案确认：

## 最终判定

- 平台侧能力：`通过 / 不通过`
- 2 小时试运行：`通过 / 条件通过 / 不通过`
- 24 小时真实联调：`通过 / 条件通过 / 不通过 / 未执行`
- 是否允许写入完成清单：`是 / 否`
- 若为否，剩余缺口：
```

## 11. 回滚和暂停策略

软暂停：

- 停止托管的 `run-im-notify-worker` 进程。
- 不删除 webhook 注册，保留 outbox backlog 和 receipt，便于恢复。
- 如需短暂停投某类事件，启动 worker 时临时减少订阅 webhook 或改用更窄的事件 webhook。

硬回滚：

- 停止 worker。
- 在 IM 侧禁用 inbound webhook 或吊销密钥。
- 保留 `runtime/integration_outbox/events.json` 和 `webhooks.json` 作为审计证据，不直接清空。
- 修复后用预览命令确认 dead-letter，再按批次 replay。

密钥风险处理：

- 立即停止 worker。
- 在接收端吊销上一版密钥。
- 用新 `--signature-key-id` 和新 `--signing-secret` 注册新 webhook。
- 原 webhook 不再用于长时 worker，待 backlog 清理和审计完成后再人工归档。

## 12. 当前缺口

- CLI daemon 是进程内循环，不负责崩溃自拉起、日志轮转和多实例互斥，生产部署需交给外部 supervisor。
- 订阅治理目前以 webhook 事件集合拆分为主，还没有按应用、版本、责任组的完整订阅配置中心。
- 真实 IM 平台的机器人限流、签名算法差异、消息格式限制需要接收端适配层吸收。
- 本地 mock/smoke 只能覆盖平台出站链路和合同，不覆盖真实 IM endpoint 的 2 小时试运行、24 小时稳定性、限流、噪声和接收方幂等运营。
- CI、缺陷和提测链路虽然已有正式入口，但仍需各自平台字段、权限和回调语义的真实适配。

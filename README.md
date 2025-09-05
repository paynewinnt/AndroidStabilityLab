# Android Stability Lab

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Entry](https://img.shields.io/badge/Entry-CLI%20%2B%20Web-2d7d46.svg)](#quick-start)
[![Tests](https://img.shields.io/badge/tests-unittest-0a7f3f.svg)](#testing)

English | [简体中文](README-CN.md)

Android Stability Lab is a local-first Android stability testing and analysis
workspace. It brings device discovery, task execution, evidence collection,
issue analysis, rule review, unattended patrols, and a lightweight web portal
into one reproducible workflow.

The project is designed for teams that need a practical lab environment before
they invest in a full online quality platform. It works well for local
debugging, team intranet demos, rule-review experiments, smoke tests, and
long-running device patrol prototypes.

> Current recommended entry points are `python -m stability.cli` and
> `python -m stability.cli serve-web`.

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Feature Highlights](#feature-highlights)
- [Project Status](#project-status)
- [Quick Start](#quick-start)
- [Common Commands](#common-commands)
- [Web Portal](#web-portal)
- [Demo Data](#demo-data)
- [Project Layout](#project-layout)
- [Testing](#testing)
- [Configuration](#configuration)
- [Security Notes](#security-notes)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Why This Exists

Android stability work often starts as a collection of shell scripts, ADB
commands, local notes, screenshots, and scattered reports. That approach is
fast at the beginning, but it becomes hard to reproduce, hand over, audit, or
run unattended.

Android Stability Lab aims to make the core workflow repeatable:

- Register devices and keep their current state visible.
- Define stability tasks and run them through a consistent execution service.
- Capture logs, reports, monitoring snapshots, traces, and issue artifacts.
- Aggregate top issues and compare versions, devices, scenarios, and metrics.
- Review analysis rules through replay, golden samples, reports, and baseline
  audits.
- Run unattended patrols and generate local daily or weekly summaries.
- Share results through a local web portal and JSON endpoints.

## Feature Highlights

### Execution and Evidence

- Device discovery through ADB and local persistence.
- Task and run lifecycle management from the CLI.
- Scenario runners for cold start loops, Monkey, install/uninstall,
  foreground/background, reboot, standby/wake, device cycle, and custom
  automation flows.
- Best-effort cleanup and retry handling for recoverable device or transport
  failures.
- Markdown and HTML report generation.
- Artifact capture for logs, bugreports, logcat, Perfetto traces, monitoring
  snapshots, and issue-specific evidence.

### Analysis and Rule Governance

- Top issue aggregation and issue-group drill-down.
- Comparison by version, device, and scenario.
- Regression judgment for issue counts and performance metrics.
- Rule configuration through local JSON files.
- Rule replay against historical runs.
- Golden sample suites for rule acceptance.
- Rule review reports with JSON, Markdown, and HTML outputs.
- Baseline promotion, rollback, history, and audit artifacts.

### Monitoring Backends

The execution pipeline can collect monitoring data through multiple backends:

- `adb_collector`: built-in ADB snapshot collection.
- `solox`: SoloX-based CPU, memory, network, battery, FPS, and GPU sampling.
- `perfetto`: Perfetto trace sidecar for deeper system-level tracing.
- `disabled`: run without monitoring.

Backend selection can be configured globally in `config/monitoring.json` or
overridden per execution with `--monitoring-backend`.

### Unattended Patrols

- Periodic task configuration with `interval_minutes`.
- Primary and fallback device selection.
- Fixed or round-robin device rotation.
- Failure thresholds, quarantine, and recovery probes.
- Single-runner lock and heartbeat files.
- Patrol history, status summaries, daily reports, and weekly reports.
- Runner-oriented web and JSON views for local duty dashboards.

### Integration Outbox

The repository includes a local integration outbox for webhook-style delivery:

- Durable event files and delivery receipts.
- Retry and dead-letter state.
- Webhook registration.
- Worker commands for local or intranet delivery.
- IM/Feishu payload contracts and smoke-test helpers.

This is intentionally a local-first integration layer. Real external endpoints
must still be validated separately before claiming production readiness.

## Project Status

The repository currently represents a functional local lab, not a complete
enterprise platform.

Recommended interpretation:

| Area | Current Scope | Not Yet Claimed |
| --- | --- | --- |
| CLI and local web | Usable for local workflows, demos, smoke tests, and team intranet sharing | Hosted SaaS, multi-tenant platform, full IAM |
| Device execution | Local ADB-driven execution and artifact capture | Fleet scheduling, quotas, approvals, maintenance windows |
| Rule governance | Local rule files, replay, golden samples, reports, baseline audits | Online rule publishing, approval workflow, staged rollout |
| IM/webhook integration | Outbox contracts, workers, mock/smoke validation | 24-hour production IM reliability without separate validation |
| SSO/identity | Trusted headers, local sessions, simple audit identity | Enterprise OIDC/LDAP/IAM and tenant isolation |
| Diagnosis | Rule-based evidence and attribution hints | AI root-cause diagnosis or production-grade intelligent triage |

## Quick Start

### Requirements

- Python 3.10+ recommended.
- ADB available in `PATH`.
- One Android device with USB debugging enabled, or a reachable TCP device.
- macOS or Linux shell environment for the bundled smoke scripts.

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Verify the CLI

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli --help
```

### Start the Web Portal

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

Then open:

- `http://127.0.0.1:8030/`
- `http://127.0.0.1:8030/health`

### Check Devices

```bash
adb devices
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-devices --sync
```

## Common Commands

Add `--help` to any command for full options.

### Tasks and Runs

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-task --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-tasks
PYTHONPATH=. ./.venv/bin/python -m stability.cli show-task --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-run --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-runs
PYTHONPATH=. ./.venv/bin/python -m stability.cli show-run --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli execute-run --help
```

### Device and Issue Queries

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-devices --sync
PYTHONPATH=. ./.venv/bin/python -m stability.cli show-device --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-top-issues --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli show-issue-group --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli compare-issues --help
```

### Performance and Regression

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli compare-performance-trends --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli judge-regression --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-analysis-snapshot --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-analysis-snapshots
```

### Rule Review and Admission

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli show-analysis-rules
PYTHONPATH=. ./.venv/bin/python -m stability.cli validate-analysis-rules
PYTHONPATH=. ./.venv/bin/python -m stability.cli diff-analysis-rules --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli replay-analysis-rules --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli verify-rule-replay-golden-samples --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-rule-review-report --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-admission-cases --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli show-admission-case --help
```

### Unattended Runner

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli configure-unattended-task --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-unattended-tasks
PYTHONPATH=. ./.venv/bin/python -m stability.cli patrol-unattended-tasks
PYTHONPATH=. ./.venv/bin/python -m stability.cli run-unattended-patrol-runner --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli build-unattended-daily-report --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli build-unattended-weekly-report --help
```

### Integration Outbox

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli register-integration-webhook --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli deliver-integration-outbox --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli run-integration-outbox-worker --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli replay-integration-dead-letters --help
```

## Web Portal

The web portal is dependency-light and intended for local or trusted intranet
use.

Common entry points:

- `/`: home dashboard.
- `/platform`: platform overview and operating notes.
- `/tasks`, `/runs`, `/artifacts`: task definitions, run history, and artifacts.
- `/performance`: monitoring snapshots, trends, and trace links.
- `/issues`: top issue aggregation and collaboration state.
- `/runner`, `/long-run-templates`: unattended patrols and long-run templates.
- `/goldens`, `/admission`, `/rules`: golden suites, admission checks, and rule governance.
- `/device-pools`, `/quick-adb`: device pools and quick ADB actions.
- `/integration`, `/doctor`: integration outbox and local diagnostics.
- `/json-api`: browser-friendly index for the current JSON API surface.

Create and update forms mark required fields in the UI and validate required
inputs before submission. Use `/json-api` as the source of truth for available
JSON endpoints instead of relying on a duplicated static endpoint list in this
README.

## Runtime Data

Runtime state is local-only. The application creates `data/` and `runtime/`
while it runs, but those directories are ignored by Git and must not be used as
source-controlled fixtures.

Local runtime locations include:

- `data/android_metrics.db`
- `data/android_metrics.db-shm`
- `data/android_metrics.db-wal`
- `runtime/admission_cases/`
- `runtime/analysis_*`
- `runtime/collaboration/`
- `runtime/integration_outbox/`
- `runtime/platform_health/`
- `runtime/tasks/`
- `runtime/unattended_runner/`
- `runtime/apks/`

These files may contain device IDs, LAN addresses, webhook secrets, package
names, APKs, logs, generated reports, and other organization-specific evidence.
Do not commit them. Sanitized examples should live under `runtime.example/` or
`tests/fixtures/`, with realistic values replaced by stable fake data.

## Project Layout

```text
AndroidStabilityLab/
├── stability/                 # Main package
│   ├── app/                   # Application services
│   ├── application/           # Higher-level orchestration helpers
│   ├── artifact/              # Artifact capture and evidence parsing
│   ├── cli/                   # CLI parser and command handlers
│   ├── domain/                # Domain models, enums, errors, value objects
│   ├── execution/             # Execution plans, hooks, state machine
│   ├── infrastructure/        # ADB, monitoring, persistence, rule config
│   ├── issue/                 # Issue detectors
│   ├── repositories/          # Repository implementations
│   ├── scenario/              # Scenario runners
│   └── web/                   # Local web portal
├── config/                    # Local JSON configuration and rule files
├── data/                      # Local SQLite database and WAL/SHM files (ignored)
├── docs/                      # Product notes, plans, runbooks
├── runtime/                   # Local reports, snapshots, runner state, artifacts (ignored)
├── runtime.example/           # Sanitized example runtime layout and notes
├── scripts/                   # Smoke and verification scripts
├── tests/                     # Python test suite and helpers
├── check_env.py               # Environment check helper
├── requirements.txt           # Runtime dependencies
└── requirements-dev.txt       # Runtime plus local developer tooling
```

The legacy `database/` package has been removed. Compatibility-facing modules
such as `core/` and `utils/` remain only as compatibility or retired entry
points. New stability features should land under `stability/`.

## Testing

Run the full test suite from the repository root:

```bash
PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests -v
```

Current local baseline:

```text
Ran 466 tests

OK
```

Run shell syntax checks for smoke scripts:

```bash
bash -n scripts/verify_v1_acceptance.sh
bash -n scripts/verify_web_portal_smoke.sh
bash -n scripts/verify_cli_query_smoke.sh
```

Common smoke entry points:

```bash
bash scripts/verify_v1_acceptance.sh
bash scripts/verify_cli_query_smoke.sh
bash scripts/verify_web_portal_smoke.sh
bash scripts/verify_monkey_smoke.sh --package-name com.example.app --device-id SERIAL
bash scripts/verify_cold_start_loop_smoke.sh --package-name com.example.app --device-id SERIAL --launch-activity .MainActivity
bash scripts/verify_install_uninstall_loop_smoke.sh --package-name com.example.app --apk-path /path/app.apk --device-id SERIAL
```

More detailed validation notes are in `tests/README.md` and `docs/`.

## Configuration

Important configuration files:

- `config/database.json`: local persistence configuration.
- `config/monitoring.json`: monitoring backend defaults.
- `config/platform.json`: platform-level local defaults.
- `config/stability_rules.json`: issue fingerprinting, regression thresholds,
  and attribution rules.
- `config/performance_risk_thresholds.json`: performance risk thresholds.
- `config/rule_review_policy.json`: rule review acceptance policy.
- `config/rule_review_baseline_policy.json`: baseline promotion policy.
- `config/rule_replay_golden_samples.json`: built-in golden replay samples.

The project favors explicit local files over hidden global state. This keeps
experiments reproducible and makes rule changes easier to review.

## Security Notes

- Do not commit runtime data or webhook secrets. `data/` and `runtime/` are
  intentionally ignored because they may contain device IDs, LAN addresses,
  logs, APKs, generated reports, and local credentials.
- Use `runtime.example/` or `tests/fixtures/` for sanitized examples only.
- The web portal is designed for local or trusted intranet use. Do not expose it
  directly to the public internet without adding authentication, authorization,
  TLS, request limits, and deployment hardening.
- Trusted-header identity support is useful for local SSO-like integration, but
  it is not a replacement for a full enterprise IAM deployment.
- IM/Feishu integration should complete real endpoint validation before being
  used as an operational alert channel.

## Roadmap

Near-term priorities:

- Tighten public packaging and installation flow.
- Add a committed license file and contribution templates.
- Keep demo fixtures smaller and easier to regenerate.
- Improve first-run onboarding for users without demo data.
- Expand real-device smoke coverage and document expected device setup.
- Harden long-running runner behavior and recovery reporting.
- Improve rule review UX in the web portal.

Longer-term possibilities:

- Optional hosted deployment profile.
- Stronger identity and access-control model.
- Richer device pool scheduling.
- Rule publishing workflow with review and rollback.
- More structured artifact indexing and retention controls.

## Contributing

Contributions are welcome, especially in these areas:

- New stability scenarios or scenario runner improvements.
- More reliable ADB and monitoring adapters.
- Better issue detectors and evidence parsers.
- Smaller, cleaner demo fixtures.
- Documentation, examples, and onboarding improvements.
- Tests that cover real workflows without requiring private devices.

Suggested workflow:

1. Open an issue or describe the change before large patches.
2. Keep changes scoped and include tests when behavior changes.
3. Run `PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests -v`.
4. For device-facing changes, also run the relevant smoke script when possible.
5. Avoid committing real secrets or private device data.

## Troubleshooting

### Python Cannot Import `stability`

Run commands from the repository root and set `PYTHONPATH=.`:

```bash
PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=. ./.venv/bin/python -m stability.cli --help
```

### ADB Device Not Found

```bash
adb devices
adb kill-server
adb start-server
adb devices
```

For TCP devices, confirm the host and port are reachable from the machine
running the lab.

### Web Portal Does Not Start

- Confirm dependencies are installed in the active virtual environment.
- Confirm the selected port is free.
- Run `PYTHONPATH=. ./.venv/bin/python -m stability.cli --help` first to verify
  CLI import and command registration.

### Reports or Runner State Look Stale

Most generated artifacts live under `runtime/`. Check:

- `runtime/unattended_runner/`
- `runtime/analysis_snapshots/`
- `runtime/analysis_review_reports/`
- `runtime/tasks/`

## License

No open-source license is granted until a `LICENSE` file is added at the
repository root. Use, redistribution, and modification rights are reserved by
the project owner unless explicitly stated otherwise.

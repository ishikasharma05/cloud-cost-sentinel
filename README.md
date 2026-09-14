# Cloud Cost Sentinel

A lightweight, cloud-agnostic agent that watches cloud spend, detects
anomalies against a rolling baseline, and alerts when something looks off —
built entirely on free-tier usage.

## Status

🚧 Work in progress — building in public, week by week.

- [x] Week 1 — AWS cost data ingestion + local storage
- [ ] Week 2 — Baseline + anomaly detection
- [ ] Week 3 — Alerting (Slack/webhook)
- [ ] Week 4 — Scheduling, docs, polish
- [ ] Later — GCP adapter, Azure adapter (pending account access)

## Why this project

Most portfolio "monitoring" projects watch servers or containers. This one
watches something every team actually cares about and rarely automates
well at small scale: cost. It's also deliberately cheap to build and run,
since it mostly reads billing APIs rather than running heavy compute.

## Architecture

The design keeps a single cloud-agnostic core (`core/engine.py`) that
doesn't know or care which cloud it's looking at. Each provider gets its
own adapter that fetches data and normalizes it into one common shape:

```python
{"provider": "aws", "service": "Amazon EC2", "date": "2026-09-13", "cost": 4.32}
```

That means adding GCP or Azure later is "write one more adapter file,"
not "rebuild the engine."

```
cloud-cost-sentinel/
├── core/           # cloud-agnostic engine, detection, alerting
├── adapters/        # one file per cloud provider
├── data/             # local cost history (JSON for now)
├── scripts/          # entry points for scheduled runs
└── docs/              # design notes and architecture diagram
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your AWS credentials
python core/engine.py  # fetches and stores the last 14 days of AWS cost data
```

Requires an AWS IAM user/role with `ce:GetCostAndUsage` permission (read-only).

## Design decisions

- **Cost Explorer over CloudWatch billing metrics** — Cost Explorer gives
  per-service daily granularity out of the box, which is what the
  anomaly detection needs; CloudWatch billing metrics are coarser.
- **JSON storage to start, SQLite later if needed** — no point adding a
  database dependency before there's a reason to query across it.
- **Rule-based detection, not ML** — a threshold/rolling-average approach
  is transparent, explainable in an interview, and doesn't need training
  data the project doesn't have yet.

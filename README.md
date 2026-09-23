# Cloud Cost Sentinel

A cloud-agnostic agent that watches cloud spend across providers, detects
anomalies against a rolling baseline, and alerts when something looks off —
built entirely on free-tier usage.

## Status

🚧 Work in progress — building in public, week by week.

- [x] Week 1 — AWS cost data ingestion (Cost Explorer) + local storage
- [x] Week 1.5 — GCP cost data ingestion (BigQuery Billing Export), wired into the same normalized pipeline
- [ ] Week 2 — Baseline + anomaly detection
- [ ] Week 3 — Alerting (Slack/webhook)
- [ ] Week 4 — Scheduling, docs, polish
- [ ] Later — Azure adapter (pending free-tier account access)

## Why this project

Most portfolio "monitoring" projects watch servers or containers. This one
watches something every team actually cares about and rarely automates
well at small scale: cost. Native tools like AWS CloudWatch billing alarms
or GCP Budgets only watch one cloud each, with a static threshold someone
has to set and re-tune by hand. This agent normalizes cost data across
providers into one pipeline and compares against a rolling baseline that
adapts on its own — and it's deliberately cheap to build and run, since it
mostly reads billing APIs rather than running heavy compute.

## Architecture

A single cloud-agnostic core (`core/engine.py`) doesn't know or care which
cloud it's looking at. Each provider gets its own adapter that fetches data
and normalizes it into one common shape:

```python
{"provider": "aws", "service": "Amazon EC2", "date": "2026-09-13", "cost": 4.32}
{"provider": "gcp", "service": "Compute Engine", "date": "2026-09-13", "cost": 1.87}
```

That means adding a new provider later is "write one more adapter file,"
not "rebuild the engine." The engine also fetches from each provider
independently — if one adapter fails (e.g. a billing export table still
initializing), the run continues with whichever providers succeeded
instead of failing entirely.
## Setup

**AWS:**
```bash
aws configure   # requires an IAM user/role with ce:GetCostAndUsage (read-only)
```

**GCP:**
```bash
gcloud auth application-default login   # no service account key needed
gcloud config set project <your-project-id>
```
Requires a BigQuery Billing Export set up on the project (Billing → Billing
export → BigQuery export), and the account used needs BigQuery Data Viewer
+ BigQuery Job User roles.

**Run it:**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 core/engine.py   # fetches and stores the last 14 days of cost data from every connected provider
```

## Design decisions

See [`docs/architecture.md`](docs/architecture.md) for the full write-up of
why each of these choices was made, including tradeoffs considered.

- **Cost Explorer over CloudWatch billing metrics** (AWS) — per-service
  daily granularity out of the box, which anomaly detection needs.
- **BigQuery Billing Export over a direct billing API** (GCP) — GCP has no
  simple "get my costs" endpoint like AWS Cost Explorer; billing export to
  BigQuery is the standard way to query cost data programmatically.
- **Application Default Credentials over a service account key** (GCP) —
  the organization enforced a policy blocking service account key creation
  (`iam.disableServiceAccountKeyCreation`); ADC via `gcloud auth
  application-default login` avoids key files entirely and is the more
  current, more secure approach anyway.
- **JSON storage to start, SQLite later if needed** — no point adding a
  database dependency before there's a reason to query across it.
- **Rule-based detection, not ML** — a threshold/rolling-average approach
  is transparent, explainable in an interview, and doesn't need training
  data the project doesn't have yet.
- **Per-provider error isolation** — one cloud's fetch failing (e.g. a
  billing export table still initializing) shouldn't stop the whole run;
  the engine logs the failure and continues with what succeeded.

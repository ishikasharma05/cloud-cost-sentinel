# Architecture & Design Decisions

## The problem

Cloud costs quietly creep up over time, and native tools don't make it easy
to catch that early:

- **AWS CloudWatch billing alarms / AWS Budgets** — work, but only watch
  AWS, and the threshold is a fixed number someone sets manually. If usage
  grows normally, the threshold either fires false alarms or has to be
  re-tuned by hand every so often.
- **GCP Budgets** — same idea, same limitation, and it's a completely
  separate system from AWS's. If a team runs workloads across both clouds
  (common), there's no single place that reasons about both together.
- Neither tool adapts to what's "normal" for a given service — they just
  compare against one static number.

## The approach

Build a small agent that:
1. Pulls daily cost data from each connected cloud provider
2. Normalizes it into one common shape, so the logic that reasons about
   the data doesn't care which cloud it came from
3. Compares each day's cost against a rolling baseline (not a fixed
   number), so the "what's normal" bar adapts automatically
4. Alerts when something deviates meaningfully from that baseline

## Why a cloud-agnostic core

The core engine (`core/engine.py`) never talks to AWS or GCP directly — it
only knows about a list of dicts in this shape:

```python
{"provider": "aws", "service": "Amazon EC2", "date": "2026-09-13", "cost": 4.32}
```

Each cloud provider gets its own adapter file
(`adapters/aws_adapter.py`, `adapters/gcp_adapter.py`) whose only job is to
fetch that provider's data and convert it into this shape. This means:

- Adding a new provider (GCP, later Azure) is "write one adapter file,"
  not "rewrite the engine."
- The detection and alerting logic, once built, works identically
  regardless of which cloud triggered it.

## AWS: Cost Explorer

Used `boto3`'s Cost Explorer client (`get_cost_and_usage`), grouped by
service, at daily granularity.

**Why Cost Explorer over CloudWatch billing metrics:** CloudWatch billing
metrics are coarser (account-level, less granular by default) and aren't
really designed for per-service daily analysis. Cost Explorer gives
per-service daily numbers directly, which is exactly what a rolling
baseline needs.

**IAM setup:** a dedicated IAM user (`cost-sentinel-agent`) with a single
custom policy granting only `ce:GetCostAndUsage` — least privilege. This
user can't do anything except read billing data; even if the credentials
leaked, the blast radius is "someone can see my AWS bill," not "someone
can touch my resources."

## GCP: BigQuery Billing Export

GCP has no direct equivalent to Cost Explorer's simple "give me my costs"
API call. The standard, Google-recommended way to query cost data
programmatically is:

1. Turn on **Billing Export to BigQuery** — GCP writes billing records
   into a BigQuery table on your project, once a day
2. Query that table with SQL from code

**Why this over alternatives:** there isn't really a simpler alternative
for daily, per-service cost data — this is the approach GCP itself
documents for programmatic billing access.

**A real constraint hit along the way:** the organization this GCP account
sits under has a policy (`iam.disableServiceAccountKeyCreation`) that
blocks creating service account key files — a security default many orgs
now enforce, since long-lived key files are a common leak vector.

Rather than needing an org admin to lift that policy, the fix was to use
**Application Default Credentials (ADC)** instead:
```bash
gcloud auth application-default login
```
This authenticates via the CLI's own OAuth flow and stores credentials
locally — no downloadable key file ever exists. Any Google client library
(including `google-cloud-bigquery`) picks these credentials up
automatically. This is arguably the better outcome anyway: it's the more
current, more secure pattern for local development, and it's a good
example of adapting the design around a real infrastructure constraint
instead of just requesting broader permissions to work around it.

**Table name auto-discovery:** GCP auto-generates the billing export
table's name (`gcp_billing_export_v1_<billing_account_id>`) rather than
letting you pick it. Instead of hardcoding that long generated name,
`gcp_adapter.py` lists the tables in the dataset and finds the one that
starts with `gcp_billing_export` at runtime — so the code isn't brittle
against a name that varies per account.

## Resilience: per-provider error isolation

`core/engine.py` wraps each provider's fetch in its own try/except. If
GCP's billing export table isn't ready yet (it can take hours to a day to
populate after first enabling), or any single provider's call fails for
any reason, the engine logs that failure and continues — it doesn't crash
the whole run or lose data already fetched from other providers. This
matters in practice: multi-cloud data sources have different reliability
and initialization timelines, and a monitoring tool that goes fully dark
because one of several inputs hiccuped defeats its own purpose.

## Storage: JSON now, SQLite later if needed

Cost history is stored as a flat JSON file, deduplicated by
`(provider, service, date)`. This is deliberately simple for the current
data volume (tens of records). If/when the project needs to query across
larger history more efficiently, or from multiple processes at once,
SQLite is the natural next step — no need to add that complexity before
there's a real reason to.

## Detection: rule-based, not ML

The planned anomaly detection (`core/detector.py`, `core/baseline.py`) is
threshold/rolling-average based — e.g. "today's cost for a service is
more than X% above its 7-day average" — rather than a trained model.

**Why:** a rule-based approach is fully explainable (important for
interviews and for actually trusting the alerts), needs no training data
this project doesn't have, and is the same fundamental idea real cost
anomaly tools (like AWS's own Cost Anomaly Detection) use under the hood.

## What's next

- Week 2: implement the actual baseline + detection rules against real
  multi-day AWS + GCP data
- Week 3: wire in Slack/webhook alerting
- Week 4: scheduling (Lambda + EventBridge or Cloud Functions + Scheduler,
  both free-tier), final polish
- Later: Azure adapter, once free-tier account access is resolved

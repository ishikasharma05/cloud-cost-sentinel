"""
gcp_adapter.py

Fetches daily GCP cost data from the BigQuery Billing Export table and
normalizes it into the same common format used by aws_adapter.py, so the
core engine doesn't need to know or care which cloud the data came from.

Auth: uses Application Default Credentials (ADC) - no key file needed.
Set up once via:
    gcloud auth application-default login
    gcloud config set project cost-sentinel

Requires the billing_export dataset to already have data flowing into it
(GCP takes a few hours to a day to populate the first rows after export
is turned on).
"""

from google.cloud import bigquery
from datetime import date, timedelta

PROJECT_ID = "cost-sentinel"
DATASET_ID = "billing_export"


def _find_billing_table(client: bigquery.Client) -> str:
    """
    GCP auto-names the billing export table like:
        gcp_billing_export_v1_XXXXXX_XXXXXX_XXXXXX
    Rather than hardcoding that long name, find it automatically.
    """
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    tables = client.list_tables(dataset_ref)

    for table in tables:
        if table.table_id.startswith("gcp_billing_export"):
            return f"{dataset_ref}.{table.table_id}"

    raise RuntimeError(
        f"No billing export table found in {dataset_ref}. "
        "Billing export may still be initializing (can take a few hours "
        "to a day after first enabling it) or hasn't been turned on."
    )


def get_daily_costs(days: int = 14) -> list[dict]:
    """
    Fetch daily cost data, grouped by service, for the last `days` days.

    Returns a list of normalized records:
        {"provider": "gcp", "service": "Compute Engine", "date": "2026-09-10", "cost": 1.23}
    """
    client = bigquery.Client(project=PROJECT_ID)
    table = _find_billing_table(client)

    start_date = (date.today() - timedelta(days=days)).isoformat()

    query = f"""
        SELECT
            DATE(usage_start_time) AS usage_date,
            service.description AS service_name,
            SUM(cost) AS total_cost
        FROM `{table}`
        WHERE DATE(usage_start_time) >= @start_date
        GROUP BY usage_date, service_name
        HAVING total_cost > 0
        ORDER BY usage_date
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        ]
    )

    results = client.query(query, job_config=job_config).result()

    records = []
    for row in results:
        records.append(
            {
                "provider": "gcp",
                "service": row.service_name,
                "date": row.usage_date.isoformat(),
                "cost": round(float(row.total_cost), 4),
            }
        )

    return records


if __name__ == "__main__":
    # Quick manual test: run `python3 adapters/gcp_adapter.py` to see real data
    data = get_daily_costs(days=7)
    if not data:
        print("No cost records yet — billing export may still be initializing.")
    for row in data:
        print(row)
    print(f"\nFetched {len(data)} records.")

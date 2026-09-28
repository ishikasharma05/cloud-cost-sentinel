"""
azure_adapter.py

Fetches daily Azure cost data from the Cost Management Query API and
normalizes it into the same common format used by the AWS and GCP adapters.

Auth: DefaultAzureCredential - picks up your `az login` session locally,
no key file needed.

Requires the AZURE_SUBSCRIPTION_ID environment variable.
NOTE: Azure bills in your account's billing currency (may be INR), unlike
AWS/GCP which are usually USD. The currency is stored on each record so
the detection logic can avoid mixing currencies.
"""

import os
from datetime import datetime, timedelta, timezone

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)


def get_daily_costs(days: int = 14) -> list[dict]:
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        raise RuntimeError(
            "AZURE_SUBSCRIPTION_ID is not set. Run: "
            "export AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)"
        )

    client = CostManagementClient(DefaultAzureCredential())
    scope = f"/subscriptions/{subscription_id}"

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    query = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(from_property=start, to=end),
        dataset=QueryDataset(
            granularity="Daily",
            aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            grouping=[QueryGrouping(type="Dimension", name="ServiceName")],
        ),
    )

    result = client.query.usage(scope, query)

    # Find columns by name instead of position, so a reordered response
    # doesn't silently break the parsing.
    cols = [c.name for c in result.columns]
    cost_i = cols.index("Cost") if "Cost" in cols else cols.index("PreTaxCost")
    date_i = cols.index("UsageDate")
    service_i = cols.index("ServiceName")
    currency_i = cols.index("Currency") if "Currency" in cols else None

    records = []
    for row in result.rows:
        cost = float(row[cost_i])
        if cost <= 0:
            continue

        raw_date = str(row[date_i])  # comes back like 20260913
        day = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"

        record = {
            "provider": "azure",
            "service": row[service_i],
            "date": day,
            "cost": round(cost, 4),
        }
        if currency_i is not None:
            record["currency"] = row[currency_i]
        records.append(record)

    return records


if __name__ == "__main__":
    data = get_daily_costs(days=7)
    if not data:
        print("No cost records yet. New accounts can take 24-48h to show data.")
    for row in data:
        print(row)
    print(f"\nFetched {len(data)} records.")

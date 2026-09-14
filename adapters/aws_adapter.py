"""
aws_adapter.py

Fetches daily AWS cost data using the Cost Explorer API and normalizes it
into a common format that the rest of the agent (and future GCP/Azure
adapters) can work with, regardless of cloud provider.

Requires an IAM user/role with the `ce:GetCostAndUsage` permission.
Credentials are picked up automatically by boto3 from:
  - environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), or
  - ~/.aws/credentials, or
  - an IAM role if running on EC2/Lambda later.
"""

import boto3
from datetime import date, timedelta


def get_daily_costs(days: int = 14) -> list[dict]:
    """
    Fetch daily cost data, grouped by service, for the last `days` days.

    Returns a list of normalized records:
        {"provider": "aws", "service": "Amazon EC2", "date": "2026-09-10", "cost": 1.23}
    """
    client = boto3.client("ce")  # Cost Explorer is region-agnostic, no region needed

    end = date.today()
    start = end - timedelta(days=days)

    response = client.get_cost_and_usage(
        TimePeriod={
            "Start": start.isoformat(),
            "End": end.isoformat(),
        },
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    records = []
    for day_result in response.get("ResultsByTime", []):
        day = day_result["TimePeriod"]["Start"]
        for group in day_result.get("Groups", []):
            service = group["Keys"][0]
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])

            # Skip zero-cost noise entries to keep the data clean
            if cost <= 0:
                continue

            records.append(
                {
                    "provider": "aws",
                    "service": service,
                    "date": day,
                    "cost": round(cost, 4),
                }
            )

    return records


if __name__ == "__main__":
    # Quick manual test: run `python adapters/aws_adapter.py` to see real data
    data = get_daily_costs(days=7)
    for row in data:
        print(row)
    print(f"\nFetched {len(data)} records.")

#!/usr/bin/env python3
"""Publish validated Hadoop Gold aggregates as a compact bank dashboard snapshot."""

import argparse
import heapq
import json
import math
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text


def _part_rows(directory: Path) -> Iterator[list[str]]:
    part_files = sorted(directory.glob("part-*"))
    if not part_files:
        raise FileNotFoundError(f"No Hadoop part files found in {directory}")
    for part_file in part_files:
        with part_file.open(encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    yield line.rstrip("\r\n").split("\t")


def _amount(value: str, source: Path) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"Invalid amount in {source}: {value!r}") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Invalid amount in {source}: {value!r}")
    return amount


def _count(value: str, source: Path) -> int:
    try:
        count = int(value)
    except ValueError:
        raise ValueError(f"Invalid count in {source}: {value!r}") from None
    if count < 0:
        raise ValueError(f"Invalid count in {source}: {value!r}")
    return count


def _json_amount(amount: Decimal) -> float:
    value = float(amount)
    if not math.isfinite(value):
        raise ValueError("Aggregate amount is outside the JSON number range")
    return value


def build_dashboard(gold_dir: Path, quality_report_path: Path) -> dict:
    quality = json.loads(quality_report_path.read_text(encoding="utf-8"))
    required_quality_fields = {"input_records", "valid_records", "rejected_records"}
    if not required_quality_fields.issubset(quality):
        raise ValueError("Silver quality report is missing record counts")
    input_records = int(quality["input_records"])
    valid_records = int(quality["valid_records"])
    rejected_records = int(quality["rejected_records"])
    if input_records != valid_records + rejected_records or rejected_records:
        raise ValueError("Silver quality report is inconsistent or contains rejected rows")

    categories = []
    approved_amount = Decimal("0")
    approved_transactions = 0
    for fields in _part_rows(gold_dir / "job1_categoria"):
        if len(fields) != 3:
            raise ValueError("Malformed category aggregate row")
        category, amount_text, count_text = fields
        amount = _amount(amount_text, gold_dir / "job1_categoria")
        count = _count(count_text, gold_dir / "job1_categoria")
        categories.append(
            {"category": category, "amount_cop": _json_amount(amount), "transactions": count}
        )
        approved_amount += amount
        approved_transactions += count

    fraud_by_city = []
    fraud_transactions = 0
    for fields in _part_rows(gold_dir / "job2_fraude"):
        if len(fields) != 2:
            raise ValueError("Malformed fraud aggregate row")
        city, count_text = fields
        count = _count(count_text, gold_dir / "job2_fraude")
        fraud_by_city.append({"city": city, "transactions": count})
        fraud_transactions += count

    top_customers: list[tuple[Decimal, int, int]] = []
    customers_with_approved_activity = 0
    customer_transactions = 0
    for fields in _part_rows(gold_dir / "job3_clientes"):
        if len(fields) != 3:
            raise ValueError("Malformed customer aggregate row")
        customer_id_text, amount_text, count_text = fields
        try:
            customer_id = int(customer_id_text)
        except ValueError:
            raise ValueError(f"Invalid customer_id in Gold output: {customer_id_text!r}") from None
        if customer_id <= 0:
            raise ValueError(f"Invalid customer_id in Gold output: {customer_id_text!r}")
        amount = _amount(amount_text, gold_dir / "job3_clientes")
        count = _count(count_text, gold_dir / "job3_clientes")
        customers_with_approved_activity += 1
        customer_transactions += count
        heapq.heappush(top_customers, (amount, customer_id, count))
        if len(top_customers) > 10:
            heapq.heappop(top_customers)

    if customer_transactions != approved_transactions:
        raise ValueError("Category and customer aggregates have different transaction counts")

    monthly_channel = []
    monthly_transactions = 0
    for fields in _part_rows(gold_dir / "job4_mensual"):
        if len(fields) != 4:
            raise ValueError("Malformed monthly aggregate row")
        month, channel, amount_text, count_text = fields
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise ValueError(f"Invalid month in Gold output: {month!r}") from None
        amount = _amount(amount_text, gold_dir / "job4_mensual")
        count = _count(count_text, gold_dir / "job4_mensual")
        monthly_channel.append(
            {
                "month": month,
                "channel": channel,
                "amount_cop": _json_amount(amount),
                "transactions": count,
            }
        )
        monthly_transactions += count

    if monthly_transactions != valid_records:
        raise ValueError("Monthly aggregates do not cover all valid Silver records")

    top = [
        {
            "customer_id": customer_id,
            "amount_cop": _json_amount(amount),
            "transactions": count,
        }
        for amount, customer_id, count in sorted(
            top_customers, key=lambda item: (-item[0], item[1])
        )
    ]
    return {
        "source": "Airflow / Hadoop MapReduce Gold",
        "quality": {
            "input_records": input_records,
            "valid_records": valid_records,
            "rejected_records": rejected_records,
        },
        "approved": {
            "amount_cop": _json_amount(approved_amount),
            "transactions": approved_transactions,
        },
        "categories": sorted(categories, key=lambda item: item["amount_cop"], reverse=True),
        "fraud": {
            "transactions": fraud_transactions,
            "by_city": sorted(
                fraud_by_city, key=lambda item: item["transactions"], reverse=True
            ),
        },
        "customers": {
            "with_approved_activity": customers_with_approved_activity,
            "top": top,
        },
        "monthly_channel": sorted(
            monthly_channel, key=lambda item: (item["month"], item["channel"])
        ),
    }


def publish_dashboard(
    gold_dir: Path, quality_report_path: Path, database_url: str
) -> None:
    payload = build_dashboard(gold_dir, quality_report_path)
    serialized_payload = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS dataset_analytics_snapshots (
                        id SMALLINT PRIMARY KEY CHECK (id = 1),
                        generated_at TIMESTAMPTZ NOT NULL,
                        payload JSONB NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO dataset_analytics_snapshots (id, generated_at, payload)
                    VALUES (1, CURRENT_TIMESTAMP, CAST(:payload AS JSONB))
                    ON CONFLICT (id) DO UPDATE
                    SET generated_at = EXCLUDED.generated_at,
                        payload = EXCLUDED.payload
                    """
                ),
                {"payload": serialized_payload},
            )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument(
        "--database-url",
        default=os.getenv("BANK_DATABASE_URL"),
        help="PostgreSQL URL; defaults to BANK_DATABASE_URL",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("BANK_DATABASE_URL or --database-url is required")
    publish_dashboard(args.gold_dir, args.quality_report, args.database_url)
    print("Published Hadoop Gold analytics to the bank database")


if __name__ == "__main__":
    main()

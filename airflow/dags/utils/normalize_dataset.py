#!/usr/bin/env python3
"""Validate and standardize the transaction array as Silver JSON Lines."""

import argparse
import json
import math
import sys
from collections import Counter
from contextlib import ExitStack, nullcontext
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator, TextIO

CHUNK_SIZE = 64 * 1024
STRING_FIELDS = (
    "merchant",
    "categoria",
    "metodo_pago",
    "ciudad",
    "canal",
)
REQUIRED_FIELDS = (
    "transaction_id",
    "fecha_hora",
    "customer_id",
    *STRING_FIELDS,
    "monto_cop",
    "estado",
    "fraude",
)
ALLOWED_STATES = {
    "aprobada": "Aprobada",
    "rechazada": "Rechazada",
    "pendiente": "Pendiente",
}


def _read_more(source: TextIO, buffer: str) -> str:
    chunk = source.read(CHUNK_SIZE)
    if not chunk:
        raise ValueError("Unexpected end of file while parsing the JSON array")
    return buffer + chunk


def iter_json_array(source: TextIO) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    buffer = source.read(CHUNK_SIZE)
    position = 0

    while True:
        while True:
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position < len(buffer):
                break
            buffer = _read_more(source, "")
            position = 0

        if buffer[position] != "[":
            raise ValueError("Dataset must be a top-level JSON array")
        position += 1
        break

    expect_record = True
    while True:
        while True:
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position < len(buffer):
                break
            buffer = _read_more(source, "")
            position = 0

        current = buffer[position]
        if current == "]":
            if expect_record and buffer[:position].rstrip().endswith(","):
                raise ValueError("Unexpected trailing comma in dataset array")
            position += 1
            trailing = buffer[position:]
            if trailing.strip() or source.read().strip():
                raise ValueError("Unexpected data after the JSON array")
            return

        if current == ",":
            if expect_record:
                raise ValueError("Unexpected comma in dataset array")
            position += 1
            expect_record = True
            continue

        if not expect_record:
            raise ValueError("Expected a comma between dataset records")

        while True:
            try:
                record, end = decoder.raw_decode(buffer, position)
                break
            except json.JSONDecodeError:
                buffer = _read_more(source, buffer)

        if not isinstance(record, dict):
            raise ValueError("Every dataset record must be a JSON object")
        yield record
        position = end
        expect_record = False
        if position >= CHUNK_SIZE:
            buffer = buffer[position:]
            position = 0


def _integer_field(record: dict, field: str) -> int:
    value = record[field]
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a positive integer") from None
    if parsed <= 0 or str(parsed) != str(value).strip():
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def normalize_record(record: dict) -> dict:
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    normalized = {
        "transaction_id": _integer_field(record, "transaction_id"),
        "customer_id": _integer_field(record, "customer_id"),
    }

    try:
        timestamp = datetime.strptime(record["fecha_hora"], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        raise ValueError("fecha_hora must use YYYY-MM-DD HH:MM:SS") from None
    normalized["fecha_hora"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    for field in STRING_FIELDS:
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        normalized[field] = value.strip()

    try:
        amount = Decimal(str(record["monto_cop"]))
    except (InvalidOperation, ValueError):
        raise ValueError("monto_cop must be a non-negative number") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("monto_cop must be a non-negative number")
    if amount == amount.to_integral_value():
        normalized["monto_cop"] = int(amount)
    else:
        normalized_amount = float(amount)
        if not math.isfinite(normalized_amount):
            raise ValueError("monto_cop must be a finite number")
        normalized["monto_cop"] = normalized_amount

    state = record["estado"]
    if not isinstance(state, str) or state.strip().casefold() not in ALLOWED_STATES:
        raise ValueError("estado must be Aprobada, Rechazada, or Pendiente")
    normalized["estado"] = ALLOWED_STATES[state.strip().casefold()]

    fraud = record["fraude"]
    if isinstance(fraud, bool):
        fraud = int(fraud)
    elif isinstance(fraud, str) and fraud.strip() in {"0", "1"}:
        fraud = int(fraud.strip())
    if not isinstance(fraud, int) or fraud not in {0, 1}:
        raise ValueError("fraude must be 0 or 1")
    normalized["fraude"] = fraud
    return normalized


def normalize_dataset(
    source_path: Path | TextIO,
    output_path: Path,
    expected_count: int,
    *,
    quarantine_path: Path | None = None,
    quality_report_path: Path | None = None,
) -> int:
    if expected_count < 0:
        raise ValueError("expected_count must not be negative")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_name(f"{output_path.name}.tmp")
    temporary_output.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
    if quality_report_path is not None:
        quality_report_path.unlink(missing_ok=True)
    if quarantine_path is not None:
        quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        quarantine_path.unlink(missing_ok=True)

    input_count = 0
    valid_count = 0
    rejected_count = 0
    rejection_reasons: Counter[str] = Counter()
    transaction_ids: set[int] = set()

    try:
        with ExitStack() as stack:
            source = stack.enter_context(
                source_path.open(encoding="utf-8")
                if isinstance(source_path, Path)
                else nullcontext(source_path)
            )
            output = stack.enter_context(
                temporary_output.open("w", encoding="utf-8", newline="\n")
            )
            quarantine = (
                stack.enter_context(
                    quarantine_path.open("w", encoding="utf-8", newline="\n")
                )
                if quarantine_path is not None
                else None
            )

            for input_count, record in enumerate(iter_json_array(source), start=1):
                try:
                    normalized = normalize_record(record)
                    transaction_id = normalized["transaction_id"]
                    if transaction_id in transaction_ids:
                        raise ValueError("duplicate transaction_id")
                    transaction_ids.add(transaction_id)
                except ValueError as error:
                    rejected_count += 1
                    rejection_reasons[str(error)] += 1
                    if quarantine is not None:
                        quarantine.write(
                            json.dumps(
                                {
                                    "row_number": input_count,
                                    "error": str(error),
                                    "record": record,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        )
                        quarantine.write("\n")
                    continue

                output.write(
                    json.dumps(
                        normalized,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                output.write("\n")
                valid_count += 1

        report = {
            "input_records": input_count,
            "valid_records": valid_count,
            "rejected_records": rejected_count,
            "rejection_reasons": dict(rejection_reasons),
        }
        if quality_report_path is not None:
            quality_report_path.parent.mkdir(parents=True, exist_ok=True)
            quality_report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        if input_count != expected_count:
            raise ValueError(
                f"Expected {expected_count:,} records, found {input_count:,}"
            )
        if rejected_count:
            raise ValueError(
                f"Rejected {rejected_count:,} of {input_count:,} records; "
                "see the quarantine and quality report"
            )

        temporary_output.replace(output_path)
        return valid_count
    finally:
        temporary_output.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        help="JSON array path, or '-' to read the array from standard input",
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-records", type=int, default=1_000_000)
    parser.add_argument("--quarantine-output", type=Path)
    parser.add_argument("--quality-report", type=Path)
    args = parser.parse_args()

    source = sys.stdin if args.source == "-" else Path(args.source)
    count = normalize_dataset(
        source,
        args.output,
        args.expected_records,
        quarantine_path=args.quarantine_output,
        quality_report_path=args.quality_report,
    )
    print(f"Validated and normalized {count:,} records to {args.output}")


if __name__ == "__main__":
    main()

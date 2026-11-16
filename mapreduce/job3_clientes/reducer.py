#!/usr/bin/env python3
"""
Job 3 - Reducer: Volumen por cliente (top spenders)
Lee pares customer_id\tmonto_cop de stdin (ya ordenados),
emite customer_id\ttotal_gastado\tnum_transacciones.
"""
import sys

def main():
    current_customer = None
    total_gastado = 0.0
    num_transacciones = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split("\t")
            if len(parts) != 2:
                print(f"ERROR: expected 2 fields, got: {line}", file=sys.stderr)
                continue
            customer_id, monto_str = parts
            monto = float(monto_str)
        except (ValueError, IndexError) as e:
            print(f"ERROR parsing reducer input: {e} — line: {line}", file=sys.stderr)
            continue

        if current_customer == customer_id:
            total_gastado += monto
            num_transacciones += 1
        else:
            if current_customer is not None:
                print(f"{current_customer}\t{total_gastado:.2f}\t{num_transacciones}")
            current_customer = customer_id
            total_gastado = monto
            num_transacciones = 1

    if current_customer is not None:
        print(f"{current_customer}\t{total_gastado:.2f}\t{num_transacciones}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Job 4 - Reducer: Volumen por mes y canal
Lee pares YYYY-MM|canal\tmonto_cop de stdin (ya ordenados),
emite mes\tcanal\ttotal_monto\tcount.
"""
import sys

def main():
    current_key = None
    total_monto = 0.0
    count = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split("\t")
            if len(parts) != 2:
                print(f"ERROR: expected 2 fields, got: {line}", file=sys.stderr)
                continue
            key, monto_str = parts
            monto = float(monto_str)
            # key is "YYYY-MM|canal"
            if "|" not in key:
                print(f"ERROR: malformed key: {key}", file=sys.stderr)
                continue
        except (ValueError, IndexError) as e:
            print(f"ERROR parsing reducer input: {e} — line: {line}", file=sys.stderr)
            continue

        if current_key == key:
            total_monto += monto
            count += 1
        else:
            if current_key is not None:
                mes, canal = current_key.split("|", 1)
                print(f"{mes}\t{canal}\t{total_monto:.2f}\t{count}")
            current_key = key
            total_monto = monto
            count = 1

    if current_key is not None:
        mes, canal = current_key.split("|", 1)
        print(f"{mes}\t{canal}\t{total_monto:.2f}\t{count}")

if __name__ == "__main__":
    main()

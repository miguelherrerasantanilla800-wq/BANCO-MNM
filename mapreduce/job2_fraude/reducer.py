#!/usr/bin/env python3
"""
Job 2 - Reducer: Detección de fraude por ciudad
Lee pares ciudad\t1 de stdin (ya ordenados),
emite ciudad\ttotal_fraudes.
"""
import sys

def main():
    current_ciudad = None
    total_fraudes = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split("\t")
            if len(parts) != 2:
                print(f"ERROR: expected 2 fields, got: {line}", file=sys.stderr)
                continue
            ciudad, count_str = parts
            count = int(count_str)
        except (ValueError, IndexError) as e:
            print(f"ERROR parsing reducer input: {e} — line: {line}", file=sys.stderr)
            continue

        if current_ciudad == ciudad:
            total_fraudes += count
        else:
            if current_ciudad is not None:
                print(f"{current_ciudad}\t{total_fraudes}")
            current_ciudad = ciudad
            total_fraudes = count

    if current_ciudad is not None:
        print(f"{current_ciudad}\t{total_fraudes}")

if __name__ == "__main__":
    main()

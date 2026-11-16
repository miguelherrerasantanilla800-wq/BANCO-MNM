#!/usr/bin/env python3
"""
Job 1 - Reducer: Total de montos por categoría
Lee pares categoria\tmonto_cop de stdin (ya ordenados),
emite categoria\ttotal_monto\tcount.
"""
import sys

def main():
    current_categoria = None
    total_monto = 0
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
            categoria, monto_str = parts
            monto = float(monto_str)
        except (ValueError, IndexError) as e:
            print(f"ERROR parsing reducer input: {e} — line: {line}", file=sys.stderr)
            continue

        if current_categoria == categoria:
            total_monto += monto
            count += 1
        else:
            if current_categoria is not None:
                print(f"{current_categoria}\t{total_monto:.2f}\t{count}")
            current_categoria = categoria
            total_monto = monto
            count = 1

    if current_categoria is not None:
        print(f"{current_categoria}\t{total_monto:.2f}\t{count}")

if __name__ == "__main__":
    main()

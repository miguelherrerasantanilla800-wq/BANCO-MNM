#!/usr/bin/env python3
"""
Job 2 - Mapper: Detección de fraude por ciudad
Lee líneas JSON de stdin, filtra transacciones con fraude==1,
emite ciudad\t1 para cada una.
"""
import sys
import json

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if record.get("fraude") == 1:
                ciudad = record.get("ciudad", "DESCONOCIDA")
                print(f"{ciudad}\t1")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"ERROR parsing line: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()

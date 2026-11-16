#!/usr/bin/env python3
"""
Job 3 - Mapper: Volumen por cliente (top spenders)
Lee líneas JSON de stdin, emite customer_id\tmonto_cop
para transacciones con estado=="Aprobada".
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
            if record.get("estado") == "Aprobada":
                customer_id = record.get("customer_id", "DESCONOCIDO")
                monto = record.get("monto_cop", 0)
                print(f"{customer_id}\t{monto}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"ERROR parsing line: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()

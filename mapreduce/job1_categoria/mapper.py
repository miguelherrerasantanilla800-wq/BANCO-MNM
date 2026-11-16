#!/usr/bin/env python3
"""
Job 1 - Mapper: Total de montos por categoría
Lee líneas JSON de stdin, emite categoria\tmonto_cop
para cada transacción con estado=="Aprobada".
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
                categoria = record.get("categoria", "DESCONOCIDA")
                monto = record.get("monto_cop", 0)
                print(f"{categoria}\t{monto}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"ERROR parsing line: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()

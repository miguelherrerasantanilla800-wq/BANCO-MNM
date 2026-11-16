#!/usr/bin/env python3
"""
Job 4 - Mapper: Volumen por mes y canal
Lee líneas JSON de stdin, extrae el mes (YYYY-MM) de fecha_hora,
emite YYYY-MM|canal\tmonto_cop.
"""
import sys
import json

def extract_month(fecha_hora: str) -> str:
    """Extrae YYYY-MM de una cadena 'YYYY-MM-DD HH:MM:SS'."""
    try:
        return fecha_hora[:7]  # 'YYYY-MM'
    except (TypeError, IndexError):
        return "UNKNOWN"

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            fecha_hora = record.get("fecha_hora", "")
            mes = extract_month(fecha_hora)
            canal = record.get("canal", "DESCONOCIDO")
            monto = record.get("monto_cop", 0)
            key = f"{mes}|{canal}"
            print(f"{key}\t{monto}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"ERROR parsing line: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()

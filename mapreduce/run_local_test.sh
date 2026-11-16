#!/usr/bin/env bash
# =============================================================================
# run_local_test.sh — Prueba local de los 4 jobs MapReduce (sin Hadoop)
# Usa pipes Unix: head | mapper | sort | reducer
# Requisito: Python 3 en PATH, dataset en la misma carpeta o pasa la ruta.
# Uso: ./run_local_test.sh [dataset_path] [num_lines]
# =============================================================================
set -euo pipefail

DATASET="${1:-/opt/airflow/data/silver/transacciones.jsonl}"
LINES="${2:-1000}"
DIR="$(cd "$(dirname "$0")" && pwd)"

# Verificar dataset
if [ ! -f "${DATASET}" ]; then
    echo "ERROR: Dataset no encontrado en '${DATASET}'"
    echo "Uso: $0 [ruta_dataset] [num_lineas]"
    exit 1
fi

echo "====================================================="
echo " Banco MNM — Prueba LOCAL de jobs MapReduce"
echo " Dataset : ${DATASET}"
echo " Líneas  : ${LINES}"
echo "====================================================="

# =============================================================================
# JOB 1: Total por categoría
# =============================================================================
echo ""
echo "--- Job 1: Total por categoría ---"
head -n "${LINES}" "${DATASET}" \
    | python3 "${DIR}/job1_categoria/mapper.py" \
    | sort \
    | python3 "${DIR}/job1_categoria/reducer.py"

# =============================================================================
# JOB 2: Fraude por ciudad
# =============================================================================
echo ""
echo "--- Job 2: Fraude por ciudad ---"
head -n "${LINES}" "${DATASET}" \
    | python3 "${DIR}/job2_fraude/mapper.py" \
    | sort \
    | python3 "${DIR}/job2_fraude/reducer.py"

# =============================================================================
# JOB 3: Volumen por cliente (top 10)
# =============================================================================
echo ""
echo "--- Job 3: Top 10 clientes por gasto ---"
head -n "${LINES}" "${DATASET}" \
    | python3 "${DIR}/job3_clientes/mapper.py" \
    | sort \
    | python3 "${DIR}/job3_clientes/reducer.py" \
    | sort -t$'\t' -k2 -rn \
    | head -10

# =============================================================================
# JOB 4: Volumen por mes y canal
# =============================================================================
echo ""
echo "--- Job 4: Volumen por mes y canal ---"
head -n "${LINES}" "${DATASET}" \
    | python3 "${DIR}/job4_mensual/mapper.py" \
    | sort \
    | python3 "${DIR}/job4_mensual/reducer.py"

echo ""
echo "====================================================="
echo " Prueba local completada."
echo "====================================================="

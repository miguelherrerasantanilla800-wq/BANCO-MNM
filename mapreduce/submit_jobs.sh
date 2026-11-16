#!/usr/bin/env bash
# =============================================================================
# submit_jobs.sh — Envía los 4 jobs MapReduce a Hadoop Streaming
# Imagen Hadoop: apache/hadoop:3.3.6
# Uso: ./submit_jobs.sh (requiere Silver previamente publicado por Airflow)
# =============================================================================
set -euo pipefail

HDFS_INPUT="/bancomnm/silver/transacciones"
HDFS_OUTPUT_BASE="/bancomnm/gold"
STREAMING_JAR="/opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-*.jar"
MAPREDUCE_DIR="$(cd "$(dirname "$0")" && pwd)"
HDFS_DATASET="${HDFS_INPUT}/dataset.jsonl"

echo "====================================================="
echo " Banco MNM — BigData MapReduce Jobs"
echo "====================================================="

# Silver debe estar validada y publicada por Airflow.
if ! hdfs dfs -test -e "${HDFS_DATASET}"; then
    echo "ERROR: Silver no encontrada en '${HDFS_DATASET}'." >&2
    echo "Ejecuta primero el DAG bancomnm_mapreduce_pipeline." >&2
    exit 1
fi
hdfs dfs -mkdir -p "${HDFS_OUTPUT_BASE}"

# =============================================================================
# JOB 1: Total por categoría
# =============================================================================
echo ""
echo "[3/6] Ejecutando Job 1: Total por categoría..."
OUTPUT_J1="${HDFS_OUTPUT_BASE}/job1_categoria"
hdfs dfs -rm -r -f "${OUTPUT_J1}" || true

hadoop jar ${STREAMING_JAR} \
    -files "${MAPREDUCE_DIR}/job1_categoria/mapper.py,${MAPREDUCE_DIR}/job1_categoria/reducer.py" \
    -mapper  "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input   "${HDFS_DATASET}" \
    -output  "${OUTPUT_J1}"

echo "--- Resultados Job 1 (Total por categoría) ---"
hdfs dfs -cat "${OUTPUT_J1}/part-*"

# =============================================================================
# JOB 2: Detección de fraude por ciudad
# =============================================================================
echo ""
echo "[4/6] Ejecutando Job 2: Fraude por ciudad..."
OUTPUT_J2="${HDFS_OUTPUT_BASE}/job2_fraude"
hdfs dfs -rm -r -f "${OUTPUT_J2}" || true

hadoop jar ${STREAMING_JAR} \
    -files "${MAPREDUCE_DIR}/job2_fraude/mapper.py,${MAPREDUCE_DIR}/job2_fraude/reducer.py" \
    -mapper  "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input   "${HDFS_DATASET}" \
    -output  "${OUTPUT_J2}"

echo "--- Resultados Job 2 (Fraude por ciudad) ---"
hdfs dfs -cat "${OUTPUT_J2}/part-*"

# =============================================================================
# JOB 3: Volumen por cliente
# =============================================================================
echo ""
echo "[5/6] Ejecutando Job 3: Volumen por cliente..."
OUTPUT_J3="${HDFS_OUTPUT_BASE}/job3_clientes"
hdfs dfs -rm -r -f "${OUTPUT_J3}" || true

hadoop jar ${STREAMING_JAR} \
    -files "${MAPREDUCE_DIR}/job3_clientes/mapper.py,${MAPREDUCE_DIR}/job3_clientes/reducer.py" \
    -mapper  "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input   "${HDFS_DATASET}" \
    -output  "${OUTPUT_J3}"

echo "--- Resultados Job 3 (Top spenders — primeras 20 líneas) ---"
hdfs dfs -cat "${OUTPUT_J3}/part-*" | head -20

# =============================================================================
# JOB 4: Volumen por mes y canal
# =============================================================================
echo ""
echo "[6/6] Ejecutando Job 4: Volumen por mes y canal..."
OUTPUT_J4="${HDFS_OUTPUT_BASE}/job4_mensual"
hdfs dfs -rm -r -f "${OUTPUT_J4}" || true

hadoop jar ${STREAMING_JAR} \
    -files "${MAPREDUCE_DIR}/job4_mensual/mapper.py,${MAPREDUCE_DIR}/job4_mensual/reducer.py" \
    -mapper  "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input   "${HDFS_DATASET}" \
    -output  "${OUTPUT_J4}"

echo "--- Resultados Job 4 (Volumen mensual por canal) ---"
hdfs dfs -cat "${OUTPUT_J4}/part-*"

echo ""
echo "====================================================="
echo " Todos los jobs completados exitosamente."
echo "====================================================="

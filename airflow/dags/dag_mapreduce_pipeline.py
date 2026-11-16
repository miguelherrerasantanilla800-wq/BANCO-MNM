"""Build Bronze and Silver transaction layers, then publish Gold aggregates."""

import os
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

HADOOP_ENV = {
    "HADOOP_HOME": "/opt/hadoop",
    "HADOOP_CONF_DIR": "/opt/hadoop/etc/hadoop",
    "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64",
    "JAVA_TOOL_OPTIONS": "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "HADOOP_USER_NAME": "hadoop",
    "DATASET_EXPECTED_RECORDS": os.getenv("DATASET_EXPECTED_RECORDS", "1000000"),
    "BANK_DATABASE_URL": os.getenv("BANK_DATABASE_URL", ""),
    "PATH": (
        "/opt/hadoop/bin:/opt/hadoop/sbin:"
        "/usr/lib/jvm/java-17-openjdk-amd64/bin:/usr/local/bin:/usr/bin:/bin"
    ),
}
BRONZE_ROOT = "/bancomnm/bronze/transacciones"
BRONZE_PATH_FILE = "/opt/airflow/data/bronze/source_path.txt"
SILVER_LOCAL = "/opt/airflow/data/silver/transacciones.jsonl"
SILVER_HDFS = "/bancomnm/silver/transacciones/dataset.jsonl"
GOLD_HDFS = "/bancomnm/gold"
MAPREDUCE_DIR = "/opt/airflow/mapreduce"


def mapreduce_task(job_name: str, display_name: str, reducers: int = 2) -> BashOperator:
    job_dir = f"{MAPREDUCE_DIR}/{job_name}"
    output_dir = f"{GOLD_HDFS}/{job_name}"
    return BashOperator(
        task_id=job_name,
        env=HADOOP_ENV,
        bash_command=f"""
set -euo pipefail
STREAMING_JAR=$(find "$HADOOP_HOME/share/hadoop/tools/lib" -maxdepth 1 -name 'hadoop-streaming-*.jar' -print -quit)
if [ -z "$STREAMING_JAR" ]; then
    echo "Hadoop Streaming JAR not found under $HADOOP_HOME" >&2
    exit 1
fi
if hdfs dfs -test -e "{output_dir}"; then
    hdfs dfs -rm -r -f "{output_dir}"
fi
hadoop jar "$STREAMING_JAR" \\
    -D mapreduce.job.name="BancoMNM-{display_name}" \\
    -D mapreduce.job.reduces={reducers} \\
    -files "{job_dir}/mapper.py,{job_dir}/reducer.py" \\
    -mapper "python3 mapper.py" \\
    -reducer "python3 reducer.py" \\
    -input "{SILVER_HDFS}" \\
    -output "{output_dir}"
hdfs dfs -ls "{output_dir}"
""",
    )


with DAG(
    dag_id="bancomnm_mapreduce_pipeline",
    description="ETL medallón: Bronze -> Silver validada -> Gold MapReduce",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "bancomnm", "retries": 1},
    tags=["bancomnm", "hadoop", "mapreduce", "medallion", "etl"],
    doc_md="""
El flujo conserva el JSON original en Bronze con una ruta identificada por SHA-256,
valida y estandariza un millón de transacciones en Silver JSON Lines, y ejecuta
cuatro agregaciones MapReduce en Gold. Los resultados Gold y el reporte de calidad
se copian al volumen compartido para el notebook de análisis exploratorio; un
snapshot validado se publica en la base bancaria para el panel de analistas.
""",
) as dag:
    ingest_bronze = BashOperator(
        task_id="ingest_bronze",
        env=HADOOP_ENV,
        bash_command=f"""
set -euo pipefail
SOURCE=/data/dataset_transacciones_1_millon.json
BRONZE_ROOT={BRONZE_ROOT}
PATH_FILE={BRONZE_PATH_FILE}
if [ ! -r "$SOURCE" ]; then
    echo "Source dataset is not readable: $SOURCE" >&2
    exit 1
fi
SOURCE_SHA=$(sha256sum "$SOURCE" | cut -d ' ' -f 1)
BRONZE_FILE="$BRONZE_ROOT/sha256=$SOURCE_SHA/dataset.json"
hdfs dfs -mkdir -p "$(dirname "$BRONZE_FILE")"
if ! hdfs dfs -test -e "$BRONZE_FILE"; then
    hdfs dfs -put "$SOURCE" "$BRONZE_FILE"
fi
mkdir -p "$(dirname "$PATH_FILE")"
printf '%s\\n' "$BRONZE_FILE" > "$PATH_FILE"
echo "Bronze source: $BRONZE_FILE"
hdfs dfs -du -h "$BRONZE_FILE"
""",
    )

    transform_silver = BashOperator(
        task_id="transform_silver",
        env=HADOOP_ENV,
        bash_command=f"""
set -euo pipefail
DATA_DIR=/opt/airflow/data/silver
BRONZE_FILE=$(cat {BRONZE_PATH_FILE})
mkdir -p "$DATA_DIR"
hdfs dfs -cat "$BRONZE_FILE" | python /opt/airflow/dags/utils/normalize_dataset.py \\
    - "{SILVER_LOCAL}" \\
    --expected-records "$DATASET_EXPECTED_RECORDS" \\
    --quarantine-output "$DATA_DIR/quarantine.jsonl" \\
    --quality-report "$DATA_DIR/quality_report.json"
hdfs dfs -rm -r -f /bancomnm/silver/transacciones
hdfs dfs -rm -f /bancomnm/silver/quality_report.json
hdfs dfs -rm -r -f /bancomnm/silver/quarantine
hdfs dfs -mkdir -p /bancomnm/silver/transacciones
hdfs dfs -put -f "{SILVER_LOCAL}" "{SILVER_HDFS}"
hdfs dfs -put -f "$DATA_DIR/quality_report.json" /bancomnm/silver/quality_report.json
if [ -s "$DATA_DIR/quarantine.jsonl" ]; then
    hdfs dfs -mkdir -p /bancomnm/silver/quarantine
    hdfs dfs -put -f "$DATA_DIR/quarantine.jsonl" /bancomnm/silver/quarantine/
fi
hdfs dfs -du -h "{SILVER_HDFS}"
""",
    )

    jobs = [
        mapreduce_task("job1_categoria", "Categoria"),
        mapreduce_task("job2_fraude", "Fraude"),
        mapreduce_task("job3_clientes", "Clientes"),
        mapreduce_task("job4_mensual", "Mensual"),
    ]

    publish_gold = BashOperator(
        task_id="publish_gold_to_notebook",
        env=HADOOP_ENV,
        bash_command=f"""
set -euo pipefail
for job in job1_categoria job2_fraude job3_clientes job4_mensual; do
    local_dir="/opt/airflow/data/gold/$job"
    mkdir -p "$local_dir"
    rm -f "$local_dir"/part-*
    hdfs dfs -get -f "{GOLD_HDFS}/$job/part-*" "$local_dir/"
done
echo "Gold results copied to /opt/airflow/data/gold"
python /opt/airflow/dags/utils/publish_dashboard.py \\
    --gold-dir /opt/airflow/data/gold \\
    --quality-report /opt/airflow/data/silver/quality_report.json \\
    --database-url "$BANK_DATABASE_URL"
""",
    )

    ingest_bronze >> transform_silver >> jobs >> publish_gold

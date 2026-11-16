# Jobs Hadoop Streaming

Los cuatro jobs de esta carpeta procesan la capa Silver JSON Lines en Hadoop Streaming. El DAG `bancomnm_mapreduce_pipeline` conserva el arreglo JSON original en Bronze, valida y estandariza Silver en streaming, y comprueba el número esperado de registros antes de ejecutar los jobs.

| Job | Agrupación | Filtro / medidas |
|---|---|---|
| `job1_categoria` | Categoría | Transacciones aprobadas; total COP y cantidad |
| `job2_fraude` | Ciudad | Transacciones marcadas como fraude; cantidad |
| `job3_clientes` | Cliente | Transacciones aprobadas; gasto total y cantidad |
| `job4_mensual` | Mes y canal | Total COP y cantidad |

## Ejecución recomendada

Levanta el stack y dispara Airflow desde la raíz del repositorio:

```powershell
docker compose up --build -d
docker compose exec airflow-webserver airflow dags unpause bancomnm_mapreduce_pipeline
docker compose exec airflow-webserver airflow dags trigger bancomnm_mapreduce_pipeline
```

El DAG carga Silver en HDFS y guarda los resultados Gold en `/bancomnm/gold/job*/`. Para leer un resultado:

```powershell
docker compose exec namenode hdfs dfs -cat /bancomnm/gold/job1_categoria/part-*
```

También se pueden volver a ejecutar los jobs manualmente después de que Airflow haya publicado Silver:

```powershell
docker compose exec namenode bash /mapreduce/submit_jobs.sh
```

El notebook `notebooks/eda_medallion.ipynb` lee Silver y las salidas Gold desde el volumen compartido `airflow_data`.

## Prueba local de una muestra

Las tuberías locales esperan JSON Lines ya normalizados:

```bash
head -n 1000 dataset.jsonl \
  | python3 mapreduce/job1_categoria/mapper.py \
  | sort \
  | python3 mapreduce/job1_categoria/reducer.py
```

Para consultar un cliente o comercio de mayor volumen, ordena la salida del reducer por el campo numérico correspondiente. No ejecutes `sort` sobre el JSON original: es un arreglo JSON, no un archivo JSON Lines.

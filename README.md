# Banco MNM — Docker, Hadoop y Airflow

Aplicación bancaria educativa con FastAPI, PostgreSQL y Nginx, más una plataforma de analítica de un millón de transacciones. El entorno local se ejecuta con Docker Compose; se incluye un stack Docker Swarm para desplegar y escalar los servicios.

## Arquitectura

| Componente | Servicios                                                                               | Función                                       |
| ---------- | --------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Banca      | `nginx`, `auth`, `bank`, `database`                                             | Frontend, APIs y datos transaccionales         |
| Hadoop     | `namenode`, 2 `datanode`, `resourcemanager`, 2 `nodemanager`, `historyserver` | HDFS y ejecución distribuida MapReduce        |
| Airflow    | `airflow-webserver`, `airflow-scheduler`, `airflow-db`                            | Orquesta Bronze → Silver → Gold y controla calidad |
| Notebook   | `notebook` (perfil opcional `analysis`)                                            | Análisis exploratorio de Silver y Gold |

El dataset fuente es un arreglo JSON de 1.000.000 de objetos. **La arquitectura Medallón son directorios de datos en HDFS; no es el notebook.** Airflow dirige la ETL, Hadoop/HDFS almacena las capas, y el notebook se usa únicamente para el análisis exploratorio de los datos ya procesados.

```text
/bancomnm/
├── bronze/
│   └── transacciones/sha256=<hash>/dataset.json
├── silver/
│   ├── transacciones/dataset.jsonl
│   ├── quality_report.json
│   └── quarantine/
└── gold/
    ├── job1_categoria/
    ├── job2_fraude/
    ├── job3_clientes/
    └── job4_mensual/
```

El DAG conserva el original en Bronze por SHA-256, valida y estandariza registros en Silver JSON Lines, y ejecuta cuatro agregaciones MapReduce en Gold. Silver incluye un reporte de calidad y una carpeta de cuarentena para registros rechazados. Al terminar, Airflow publica un snapshot agregado en `banco_db`; el panel **Analista** consume ese snapshot por `/api/global/dataset`. El panel de cliente sigue mostrando únicamente los movimientos asociados a su cuenta. El notebook solo lee Silver y Gold para hacer el análisis exploratorio.

## Requisitos

- Docker Desktop con Docker Compose v2.
- 8 GB de memoria disponibles como mínimo; 10 GB recomendados para ejecutar Hadoop, Airflow y la aplicación juntos.
- El archivo `dataset_transacciones_1_millon.json` en la raíz.
- Para ejecutar pruebas locales: Python 3.10+ y las dependencias de desarrollo.

## Inicio rápido (PowerShell)

```powershell
.\start.ps1
```

El script conserva los valores que ya tengas en `.env`, genera los secretos faltantes y ejecuta Compose. Guarda la contraseña de Airflow que muestra al final. La primera ejecución descarga y construye las imágenes; las siguientes solo inician los contenedores.

Para reconstruir imágenes después de modificar código:

```powershell
.\start.ps1 -Build
docker compose ps
```

Hadoop formatea el NameNode solo al inicializar su volumen vacío. Para detener y conservar datos:

```powershell
docker compose down
```

Para borrar también los datos persistidos (irreversible):

```powershell
docker compose down -v
```

## Interfaces

| Servicio             | URL                        | Acceso                                       |
| -------------------- | -------------------------- | -------------------------------------------- |
| Aplicación          | http://localhost:8080      | Frontend y APIs vía Nginx                   |
| AUTH API             | http://localhost:8001/docs | Documentación OpenAPI                       |
| BANCO API            | http://localhost:8002/docs | Documentación OpenAPI                       |
| Airflow              | http://localhost:8083      | Usuario/contraseña configurados en `.env` |
| HDFS NameNode        | http://localhost:9870      | Estado de HDFS                               |
| YARN ResourceManager | http://localhost:8088      | Estado de jobs/recursos                      |
| MapReduce History    | http://localhost:19888     | Historial de jobs                            |

Los servicios de Hadoop y las APIs se publican solo en loopback en Compose; la interfaz bancaria usa el puerto `HTTP_PORT` (8080 por defecto).

El frontend ofrece resumen de saldo, ingresos y egresos, lecturas descriptivas del historial, gráficos y movimientos recientes. Sus términos y aviso de privacidad son informativos para el prototipo: no existe canal de atención de derechos ni registro de autorización legal. No uses datos reales; antes de producción se deben definir el responsable, sus datos de contacto y los procesos de protección de datos, con revisión jurídica.

## ETL medallón con Airflow

Activa el DAG `bancomnm_mapreduce_pipeline` si aparece pausado y ejecútalo desde PowerShell:

```powershell
docker compose exec airflow-webserver airflow dags unpause bancomnm_mapreduce_pipeline
docker compose exec airflow-webserver airflow dags trigger bancomnm_mapreduce_pipeline
```

El DAG sigue estas capas:

- **Bronze:** copia sin transformar del JSON original en `/bancomnm/bronze/transacciones/sha256=<hash>/dataset.json`. Las rutas por hash conservan versiones distintas de la fuente.
- **Silver:** `/bancomnm/silver/transacciones/dataset.jsonl`, normalizada y validada en streaming. El reporte de calidad queda en `/bancomnm/silver/quality_report.json`; los datos rechazados se conservan en `/bancomnm/silver/quarantine/`. Si hay filas inválidas, el DAG falla antes de ejecutar Gold.
- **Gold:** resultados MapReduce en `/bancomnm/gold/job1_categoria`, `job2_fraude`, `job3_clientes` y `job4_mensual`.
- **Dashboard:** el DAG valida los conteos de Gold, prepara un resumen pequeño y lo publica transaccionalmente en PostgreSQL. El panel Analista muestra la calidad de los 1.000.000 de registros, monto aprobado por categoría, fraude por ciudad, actividad mensual por canal y los 10 clientes con mayor monto aprobado. Es analítica global del dataset, no información personal de cuentas bancarias.

Consulta las capas y los agregados desde PowerShell:

```powershell
docker compose exec namenode hdfs dfs -ls -R /bancomnm/bronze
docker compose exec namenode hdfs dfs -cat /bancomnm/silver/quality_report.json
docker compose exec namenode hdfs dfs -cat /bancomnm/gold/job1_categoria/part-*
docker compose exec namenode hdfs dfs -cat /bancomnm/gold/job2_fraude/part-*
docker compose exec namenode hdfs dfs -cat /bancomnm/gold/job3_clientes/part-*
docker compose exec namenode hdfs dfs -cat /bancomnm/gold/job4_mensual/part-*
```

Consulta las ejecuciones en Airflow (`http://localhost:8083`), YARN (`http://localhost:8088`) y el historial de MapReduce (`http://localhost:19888`). Silver y los archivos Gold para análisis también se publican en el volumen compartido `airflow_data`.

## Notebook de análisis exploratorio

Con el stack levantado y una ejecución exitosa del DAG, inicia el servicio opcional de Jupyter:

```powershell
docker compose --profile analysis up --build -d notebook
docker compose logs notebook
```

Abre `http://localhost:8889` usando el token que aparece en los logs y abre `eda_medallion.ipynb`. El notebook **no ejecuta la ETL ni crea las capas**: solo lee `/data/silver` y `/data/gold` (publicadas previamente por Airflow en `airflow_data`), escanea Silver en fragmentos de 100.000 filas y grafica los agregados Gold. El servicio solo se inicia al activar el perfil `analysis`; para detenerlo ejecuta `docker compose stop notebook`.

Al reprocesar, Bronze se conserva por hash de contenido; Silver y Gold reflejan la última ejecución exitosa.

## Docker Swarm

`docker-stack.yml` despliega la plataforma completa en modo Swarm. Requiere que las imágenes de la aplicación, Hadoop (con Python para los mappers) y Airflow estén disponibles en todos los nodos. Construye las imágenes con Compose, publícalas en un registry y configura `APP_IMAGE`, `HADOOP_IMAGE` y `AIRFLOW_IMAGE` con las referencias publicadas. `docker stack deploy` no construye imágenes ni carga automáticamente el archivo `.env`.

Construye las imágenes y publícalas en un registry accesible desde cada nodo. Ejecuta estos pasos en un manager Linux con el repositorio y el dataset disponibles localmente:

```bash
set -a
source .env
set +a
export APP_IMAGE=registry.example/bancomnm/app:1.0
export HADOOP_IMAGE=registry.example/bancomnm/hadoop:1.0
export AIRFLOW_IMAGE=registry.example/bancomnm/airflow:1.0
export DATASET_HOST_PATH="$PWD/dataset_transacciones_1_millon.json"
docker compose build auth namenode airflow-init
docker compose push auth namenode airflow-init
docker node update --label-add bancomnm-data=true "$(docker node ls --filter role=manager --format '{{.ID}}' | head -n 1)"
docker stack deploy -c docker-stack.yml bancomnm
```

Al usar Swarm, configura en la terminal las variables de `.env` (`POSTGRES_PASSWORD`, `JWT_SECRET`, secretos de Airflow y referencias de imagen) antes del despliegue. Las rutas de `dataset`, `frontend`, `nginx` y `database/init` deben existir en el manager Linux.

El stack coloca las bases de datos, HDFS y Airflow en el nodo etiquetado porque sus volúmenes usan almacenamiento local. Las APIs son replicables:

```powershell
docker service scale bancomnm_auth=3 bancomnm_bank=3
docker stack services bancomnm
docker stack rm bancomnm
```

Esto es una configuración educativa de nodo único para los servicios con estado, no alta disponibilidad. Para distribuir HDFS entre nodos, configura almacenamiento persistente accesible por nodo y ajusta las restricciones de colocación. No publiques los puertos de Hadoop/Airflow ni uses esta configuración sin TLS, gestión de secretos y controles de red en producción.

## Desarrollo y pruebas

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements-dev.txt
$env:PYTHONPATH = (Resolve-Path app).Path
.\.venv\Scripts\python.exe -m pytest app/tests airflow/dags/utils/test_publish_dashboard.py -q
```

El entorno virtual evita que versiones globales incompatibles de FastAPI, Starlette o HTTPX afecten las pruebas.
La prueba local de mappers/reducers está descrita en [`mapreduce/README.md`](mapreduce/README.md). La prueba de API usa SQLite temporal; para integración real se necesita el stack Compose.

## Estructura

```text
.
├── airflow/
│   ├── Dockerfile
│   └── dags/
├── notebooks/              # Notebook EDA y servicio Jupyter opcional
├── app/
├── database/init/
├── hadoop/                 # Configuración de HDFS, YARN y MapReduce
├── mapreduce/              # Mappers, reducers y pruebas locales
├── docker-compose.yml      # Desarrollo: banca + Hadoop + Airflow
├── docker-stack.yml        # Despliegue Docker Swarm
└── dataset_transacciones_1_millon.json
```

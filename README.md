# Banco MNM — Docker, Hadoop y Airflow

Aplicación bancaria educativa con FastAPI, PostgreSQL y Nginx, más una plataforma de analítica de un millón de transacciones. El entorno local se ejecuta con Docker Compose; se incluye un stack Docker Swarm para desplegar y escalar los servicios.

## Arquitectura

| Componente | Servicios | Función |
|---|---|---|
| Banca | `nginx`, `auth`, `bank`, `database` | Frontend, APIs y datos transaccionales |
| Hadoop | `namenode`, 2 `datanode`, `resourcemanager`, 2 `nodemanager`, `historyserver` | HDFS y ejecución distribuida MapReduce |
| Airflow | `airflow-webserver`, `airflow-scheduler`, `airflow-db` | Orquesta Bronze → Silver → Gold y controla calidad |
| Notebook | `notebook` (perfil opcional `analysis`) | Análisis exploratorio de Silver y Gold |
| Observabilidad | `docker-exporter`, `cadvisor`, `prometheus`, `grafana` | Métricas de recursos de los contenedores |

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

- Docker Engine con el complemento Docker Compose v2 en Linux, o Docker Desktop en Windows.
- 8 GB de memoria disponibles como mínimo; 10 GB recomendados para ejecutar Hadoop, Airflow y la aplicación juntos.
- El archivo `dataset_transacciones_1_millon.json` en la raíz.
- Bash y Python 3.10+ para el inicio en Linux y las pruebas locales.

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

### Inicio en Linux (Docker Compose)

Instala Docker Engine y el complemento Compose v2 siguiendo la [guía oficial de Docker](https://docs.docker.com/engine/install/). Si tu usuario necesita acceso directo al daemon, puedes agregarlo al grupo `docker` y volver a iniciar sesión:

```bash
sudo usermod -aG docker "$USER"
```

El grupo `docker` equivale a acceso de administrador; úsalo solo con cuentas de confianza. Confirma los requisitos antes de continuar:

```bash
docker --version
docker compose version
python3 --version
```

Desde la raíz del proyecto, asegúrate de que `dataset_transacciones_1_millon.json` esté presente y ejecuta:

```bash
chmod +x start.sh
./start.sh
```

En la primera ejecución, `start.sh` crea `.env` a partir de `.env.example`, genera secretos aleatorios y restringe los permisos del archivo. No sobrescribe un `.env` existente; si este todavía contiene valores de ejemplo, reemplázalos antes de iniciar. El script construye las imágenes necesarias y muestra el estado de los servicios. Para reconstruir después de cambiar código:

```bash
./start.sh
# O, si ya tienes las imágenes y quieres omitir la compilación:
./start.sh --no-build
```

Comprueba el estado y sigue los logs del scheduler:

```bash
docker compose ps
docker compose logs -f airflow-scheduler
```

La aplicación queda en `http://localhost:8080`. Para detener los servicios conservando los datos:

```bash
docker compose down
```

`docker compose down --volumes` también elimina las bases de datos y los datos de HDFS; úsalo solo cuando quieras borrarlos de forma permanente. El inicio con `start.sh` es Docker Compose de un solo host, no despliega Docker Swarm ni proporciona alta disponibilidad.

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
| Prometheus           | http://localhost:9090      | Recolección y consulta de métricas         |
| Grafana              | http://localhost:3000      | Usuario/contraseña configurados en `.env` |

Los servicios de Hadoop y las APIs se publican solo en loopback en Compose; la interfaz bancaria usa el puerto `HTTP_PORT` (8080 por defecto).

### Observabilidad de contenedores

Compose inicia cAdvisor, Prometheus y Grafana junto con el resto de la plataforma. cAdvisor recolecta métricas de CPU, memoria, red y filesystem; Prometheus las conserva durante 15 días. Grafana carga automáticamente la fuente Prometheus y el dashboard **Infrastructure → Contenedores Docker**.

Configura `GRAFANA_ADMIN_USER` y `GRAFANA_ADMIN_PASSWORD` en `.env` antes de iniciar el stack. Las interfaces de Grafana y Prometheus solo escuchan en `localhost`; no expongas cAdvisor ni estos puertos directamente a Internet. Para arrancar o actualizar los servicios ejecuta `.\start.ps1`.

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

Compose prepara los permisos del volumen compartido `airflow_data` para el usuario de Airflow antes de iniciar el scheduler; no elimines ese volumen si quieres conservar Silver y Gold para el notebook.

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

`docker-stack.yml` requiere al menos tres nodos Linux Swarm y un servidor NFSv4 accesible desde todos ellos. Se recomienda que los tres nodos sean managers para conservar el quorum del plano de control si falla uno. Etiqueta cada nodo de cómputo con una zona distinta; Swarm distribuye las réplicas de Nginx, AUTH, BANCO y los DataNodes entre ellas. La API bancaria tiene tres réplicas y usa el endpoint virtual (VIP) de Swarm: Nginx se conecta a `bank:8002` y Swarm balancea las conexiones entre las tareas disponibles. El modo `ingress` del puerto publicado de Nginx balancea también las solicitudes hacia sus réplicas. `docker-compose.yml` sirve para desarrollo local y mantiene una sola réplica de la API; el Docker Desktop de un solo nodo no demuestra balanceo multinodo ni alta disponibilidad.

### Simulación local de recuperación (Docker-in-Docker)

En este laboratorio hay un Swarm anidado con tres contenedores Docker-in-Docker: `bancomnm-sim-manager`, `bancomnm-sim-worker1` y `bancomnm-sim-worker2`. Requiere contenedores privilegiados y es solo para pruebas educativas. El volumen local `bancomnm-sim-shared` se monta en los tres nodos bajo `/shared` para simular almacenamiento compartido:

- `bancomnm-sim-web`: servicio Nginx de prueba, tres réplicas.
- `bancomnm-sim-postgres`: una instancia PostgreSQL de prueba, con datos en `/shared/postgres` y respaldos de prueba en `/shared/backups`.

La prueba realizada creó respaldos sintéticos de `auth_db` y `banco_db`, ejecutó `database/restore.sh` y verificó los datos restaurados. Después se detuvo el worker que alojaba PostgreSQL: Swarm reubicó la tarea, PostgreSQL volvió a aceptar conexiones y el dato de prueba persistió. Al reiniciar el worker, los tres nodos quedaron `Ready`; PostgreSQL quedó `1/1` y Nginx `3/3`.

Si los contenedores de la simulación ya existen pero están detenidos, puedes iniciarlos desde PowerShell:

```powershell
docker start bancomnm-sim-manager bancomnm-sim-worker1 bancomnm-sim-worker2
```

Consulta el estado:

```powershell
docker exec bancomnm-sim-manager docker node ls
docker exec bancomnm-sim-manager docker service ls
docker exec bancomnm-sim-manager docker service ps bancomnm-sim-postgres
docker exec bancomnm-sim-manager docker service ps bancomnm-sim-web
```

Esta simulación local no se crea con `start.ps1` ni se despliega desde `docker-stack.yml`.

Para repetir la prueba de recuperación, mueve primero PostgreSQL a `worker1` drenando temporalmente el manager y `worker2`. Espera a que `docker service ps` muestre la tarea `Running` en `worker1`; luego reactiva los otros nodos antes de detener ese worker:

```powershell
docker exec bancomnm-sim-manager docker node update --availability drain manager
docker exec bancomnm-sim-manager docker node update --availability drain worker2
docker exec bancomnm-sim-manager docker service ps bancomnm-sim-postgres
# Cuando PostgreSQL esté Running en worker1:
docker exec bancomnm-sim-manager docker node update --availability active manager
docker exec bancomnm-sim-manager docker node update --availability active worker2
docker stop bancomnm-sim-worker1
docker exec bancomnm-sim-manager docker service ps bancomnm-sim-postgres
# Espera una tarea Running en manager o worker2; después reinicia worker1.
docker start bancomnm-sim-worker1
docker exec bancomnm-sim-manager docker node ls
```

No detengas `bancomnm-sim-manager`: es el único manager de esta simulación. El volumen compartido es local al mismo equipo, no NFS; por tanto, la prueba solo demuestra recuperación de una tarea ante la caída simulada de un worker. No despliega la aplicación bancaria, no sobrevive a la caída física del equipo y no sustituye la prueba del stack real con NFSv4 y hosts Linux independientes. Los servicios `bancomnm-sim-*` son independientes del stack real `bancomnm` y de `web_stack`.

### Preparar los nodos y el contexto Docker

Instala Docker Engine en los tres nodos Linux. En el primer manager inicializa el clúster usando su IP privada:

```bash
docker swarm init --advertise-addr <IP_PRIVADA_MANAGER_1>
docker swarm join-token manager
```

En los otros dos nodos ejecuta el comando `docker swarm join` que muestra el manager. Mantén privado el token de unión. Verifica desde el manager:

```bash
docker node ls
```

Permite únicamente entre los nodos Swarm TCP/2377, TCP y UDP/7946, y UDP/4789. Permite TCP/2049 entre los nodos y el servidor NFS. Publica los puertos de la aplicación solo en las redes que deban acceder a ellos.

Desde la máquina de despliegue, crea un contexto SSH hacia ese manager (requiere una clave SSH configurada y que el usuario remoto pueda usar Docker):

```bash
docker context create maelxd --docker "host=ssh://<USUARIO>@<IP_PRIVADA_MANAGER_1>"
docker --context maelxd info --format '{{.Name}} {{.Swarm.LocalNodeState}} {{.Swarm.ControlAvailable}}'
docker --context maelxd node ls
```

Si el contexto `maelxd` ya existe, no lo vuelvas a crear: revisa `docker context ls` y úsalo con `docker context use maelxd`. No compartas la clave privada SSH ni los tokens de unión.

### Preparar NFS

Define `NFS_SERVER` con la IP del servidor y `NFS_EXPORT_PATH=/bancomnm` en `.env`. `NFS_EXPORT_PATH` es la ruta visible desde la raíz virtual de NFSv4, no la ruta física del servidor. El ejemplo siguiente exporta `/srv/nfs` como raíz virtual y guarda los datos físicamente en `/srv/nfs/bancomnm`. Permite NFS TCP/2049 solo desde la subred de los nodos. Prepara los permisos antes de desplegar; las imágenes usan estos UID/GID:

| Ruta | Propietario |
|---|---:|
| `postgres`, `database-backups`, `airflow-postgres` | `70:70` |
| `namenode`, `historyserver` | `1000:1000` |
| `airflow-data` | `50000:0` |
| `prometheus` | `65534:65534` |
| `grafana` | `472:0` |

El directorio `datasets` debe contener `dataset_transacciones_1_millon.json` y permitir lectura a todos los nodos. Los montajes PostgreSQL son de un solo escritor. NFS debe ofrecer escrituras durables y también alta disponibilidad; un único servidor NFS sigue siendo un punto único de falla. Conserva una copia de los respaldos fuera del mismo servidor/export NFS para recuperarte de la pérdida de ese almacenamiento.

Ejemplo de preparación en el servidor NFS (ajusta la ruta y la subred; exporta cada subdirectorio a los nodos Swarm):

```bash
sudo mkdir -p /srv/nfs/bancomnm/{postgres,database-backups,namenode,historyserver,airflow-postgres,airflow-data,datasets,prometheus,grafana}
sudo chown 70:70 /srv/nfs/bancomnm/{postgres,database-backups,airflow-postgres}
sudo chmod 700 /srv/nfs/bancomnm/{postgres,database-backups,airflow-postgres}
sudo chown 1000:1000 /srv/nfs/bancomnm/{namenode,historyserver}
sudo chown 50000:0 /srv/nfs/bancomnm/airflow-data
sudo chown 65534:65534 /srv/nfs/bancomnm/prometheus
sudo chown 472:0 /srv/nfs/bancomnm/grafana
sudo chmod 770 /srv/nfs/bancomnm/{airflow-data,prometheus,grafana}
sudo chmod 755 /srv/nfs/bancomnm/datasets
```

En Ubuntu/Debian, instala `nfs-kernel-server` en el servidor NFS y `nfs-common` en cada nodo Swarm:

```bash
sudo apt-get update
sudo apt-get install -y nfs-kernel-server # servidor NFS
sudo apt-get install -y nfs-common        # cada nodo Swarm
```

Configura `/etc/exports` en el servidor NFS para crear una raíz virtual `fsid=0` y exportar cada subdirectorio a la subred privada. Sustituye `10.0.0.0/24` por la subred real:

```text
/srv/nfs 10.0.0.0/24(ro,fsid=0,crossmnt,no_subtree_check)
/srv/nfs/bancomnm/postgres 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/database-backups 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/namenode 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/historyserver 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/airflow-postgres 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/airflow-data 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/datasets 10.0.0.0/24(ro,sync,no_subtree_check)
/srv/nfs/bancomnm/prometheus 10.0.0.0/24(rw,sync,no_subtree_check)
/srv/nfs/bancomnm/grafana 10.0.0.0/24(rw,sync,no_subtree_check)
```

Aplica `sudo exportfs -ra` y verifica `sudo exportfs -v`. Desde cada nodo, monta temporalmente `NFS_SERVER:/bancomnm/datasets` y confirma que se ve el dataset; desmonta después. Copia el archivo al directorio físico `/srv/nfs/bancomnm/datasets` antes de iniciar el DAG. Ajusta la ruta física si tu servidor usa otra ubicación y mantén `NFS_EXPORT_PATH` coherente con la ruta visible bajo la raíz `fsid=0`.

### Construir y desplegar

Publica las imágenes en un registry accesible por todos los nodos. Sustituye `registry.example` por el host real del registry y `bancomnm` por el namespace que te corresponda; `docker stack deploy` no construye imágenes ni carga `.env`.

```bash
set -a
source .env
set +a
export APP_IMAGE=registry.example/bancomnm/app:1.0
export HADOOP_IMAGE=registry.example/bancomnm/hadoop:1.0
export AIRFLOW_IMAGE=registry.example/bancomnm/airflow:1.0
export NGINX_IMAGE=registry.example/bancomnm/nginx:1.0
export MONITORING_IMAGE=registry.example/bancomnm/monitoring:1.0
docker login registry.example
docker --context default compose build auth namenode airflow-init docker-exporter
docker --context default compose push auth namenode airflow-init docker-exporter
docker --context default build -f nginx/Dockerfile -t "$NGINX_IMAGE" .
docker --context default push "$NGINX_IMAGE"
docker context use maelxd
docker node ls
docker node update --label-add bancomnm.zone=zone-a <nodo-1>
docker node update --label-add bancomnm.zone=zone-b <nodo-2>
docker node update --label-add bancomnm.zone=zone-c <nodo-3>
docker stack deploy --with-registry-auth -c docker-stack.yml bancomnm
```

Antes del despliegue, copia el dataset a la ruta NFS `datasets`. El stack empaqueta el frontend y la configuración Nginx en su imagen; HDFS, Prometheus y Grafana reciben su configuración mediante Docker configs, así que esos archivos no necesitan existir en los workers.

Comprueba el estado y la distribución:

```bash
docker stack services bancomnm
docker service ps bancomnm_auth
docker service ps bancomnm_bank
docker service ps bancomnm_datanode
docker service logs bancomnm_database-backup
```

### Alta disponibilidad y recuperación

- Nginx, AUTH y BANCO tienen tres réplicas, una por zona, healthchecks, reinicio automático y rollback en actualizaciones fallidas. Si se pierde un nodo, las réplicas restantes mantienen la capacidad de servicio; si allí estaba PostgreSQL, las operaciones de datos pueden interrumpirse hasta que su única tarea se recupere.
- HDFS tiene tres DataNodes con replicación de bloques `2`; sus discos son locales y una réplica nueva puede reconstruir bloques desde los nodos supervivientes. Los metadatos del NameNode persisten en NFS. YARN ResourceManager y Airflow Scheduler reinician si fallan; Airflow reintenta tareas fallidas.
- PostgreSQL es un servicio de un solo escritor sobre NFS compartido. Swarm puede reubicarlo y conservar sus datos, pero habrá una interrupción mientras reinicia; esto **no** es failover de PostgreSQL sin corte. Un servicio de respaldo crea dumps validados de `auth_db` y `banco_db` cada seis horas y conserva siete días.

Para comprobar la tolerancia a la pérdida de un worker, drena un nodo y verifica que el gateway siga respondiendo y que las tareas se reubiquen; después vuelve a habilitarlo:

```bash
docker node update --availability drain <nodo>
docker stack services bancomnm
docker node update --availability active <nodo>
```

La aplicación tolera la pérdida de un nodo con capacidad restante, pero una caída de NFS interrumpe los datos persistidos. Para HA estricta de base de datos sin interrupción se necesita además replicación/failover PostgreSQL y un backend NFS redundante; el stack actual ofrece recuperación automática y restauración desde backups, no esas garantías.

Prometheus y Grafana también se despliegan en Swarm; `docker-exporter` y cAdvisor corren globalmente y Prometheus descubre las tareas por DNS de Swarm. Restringe por firewall los puertos publicados y protege el acceso al socket Docker montado por el exporter.

Para restaurar ambos dumps más recientes (reemplaza objetos y datos en las dos bases; pruébalo primero en un entorno aislado):

```bash
docker service ps bancomnm_database-backup
# En el nodo que ejecuta la tarea:
docker ps --filter label=com.docker.swarm.service.name=bancomnm_database-backup
docker exec -it <container-id> sh /opt/restore.sh
```

Para eliminar el stack:

```bash
docker stack rm bancomnm
```

El estado y los volúmenes NFS sobreviven a `docker stack rm`; no borres las rutas del servidor salvo que quieras eliminar permanentemente esos datos. Esta es una configuración educativa, no sustituye TLS, gestión de secretos, fencing del nodo fallido, almacenamiento NFS redundante ni pruebas periódicas de restauración en producción.

## Desarrollo y pruebas

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements-dev.txt
$env:PYTHONPATH = (Resolve-Path app).Path
.\.venv\Scripts\python.exe -m pytest app/tests airflow/tests airflow/dags/utils -q
```

El entorno virtual evita que versiones globales incompatibles de FastAPI, Starlette o HTTPX afecten las pruebas.
La prueba local de mappers/reducers está descrita en [`mapreduce/README.md`](mapreduce/README.md). La prueba de API usa SQLite temporal; para integración real se necesita el stack Compose.

En Linux, usa el mismo entorno aislado con:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements-dev.txt
PYTHONPATH="$PWD/app" .venv/bin/python -m pytest app/tests airflow/tests airflow/dags/utils -q
```

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

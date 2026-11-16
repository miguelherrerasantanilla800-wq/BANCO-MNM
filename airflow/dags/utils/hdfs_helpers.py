"""
utils/hdfs_helpers.py
Módulo de funciones helper para interactuar con HDFS
en el proyecto Banco MNM BigData.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración por defecto
# ---------------------------------------------------------------------------
HADOOP_HOME  = os.environ.get("HADOOP_HOME", "/opt/hadoop")
HDFS_URL     = os.environ.get("HDFS_URL", "hdfs://namenode:8020")
HADOOP_BIN   = os.path.join(HADOOP_HOME, "bin", "hdfs")

_DEFAULT_ENV = {
    "HADOOP_HOME": HADOOP_HOME,
    "PATH": f"{HADOOP_HOME}/bin:{HADOOP_HOME}/sbin:/usr/local/bin:/usr/bin:/bin",
    "JAVA_HOME": os.environ.get("JAVA_HOME", "/usr/lib/jvm/java-11-openjdk-amd64"),
}


# ===========================================================================
# Clase cliente HDFS (wrapper de subprocess)
# ===========================================================================

class HdfsClient:
    """
    Cliente HDFS ligero basado en subprocess.
    Envuelve llamadas a `hdfs dfs` para usarlas desde Python
    sin dependencias de librerías externas pesadas.

    Uso típico:
        client = get_hdfs_client()
        client.mkdir("/bancomnm/input")
        client.put("/local/file.json", "/bancomnm/input/file.json")
        lines = client.cat("/bancomnm/output/job1/part-00000")
    """

    def __init__(self, namenode_url: str = HDFS_URL, env: Optional[Dict] = None):
        self.namenode_url = namenode_url
        self.env = {**_DEFAULT_ENV, **(env or {})}

    def _run(self, *hdfs_args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Ejecuta un comando `hdfs dfs ...` y retorna el resultado."""
        cmd = [HADOOP_BIN, "dfs"] + list(hdfs_args)
        logger.debug("HDFS CMD: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self.env,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"HDFS error (rc={result.returncode}): {result.stderr.strip()}"
            )
        return result

    def mkdir(self, hdfs_path: str) -> bool:
        """Crea un directorio en HDFS (con -p para padres)."""
        try:
            self._run("-mkdir", "-p", hdfs_path)
            logger.info("HDFS mkdir: %s", hdfs_path)
            return True
        except RuntimeError as exc:
            logger.error("mkdir failed for %s: %s", hdfs_path, exc)
            return False

    def exists(self, hdfs_path: str) -> bool:
        """Retorna True si la ruta existe en HDFS."""
        result = self._run("-test", "-e", hdfs_path, check=False)
        return result.returncode == 0

    def ls(self, hdfs_path: str) -> List[str]:
        """Lista los archivos/directorios en hdfs_path."""
        result = self._run("-ls", hdfs_path, check=False)
        if result.returncode != 0:
            return []
        lines = []
        for line in result.stdout.strip().split("\n"):
            # Las líneas de ls tienen formato: perms replicas user group size date path
            parts = line.split()
            if len(parts) >= 8:
                lines.append(parts[-1])
        return lines

    def put(self, local_path: str, hdfs_path: str, overwrite: bool = True) -> bool:
        """Sube un archivo local a HDFS."""
        args = ["-put"]
        if overwrite:
            args.append("-f")
        args += [local_path, hdfs_path]
        try:
            self._run(*args)
            logger.info("HDFS put: %s → %s", local_path, hdfs_path)
            return True
        except RuntimeError as exc:
            logger.error("put failed: %s", exc)
            return False

    def get(self, hdfs_path: str, local_path: str) -> bool:
        """Descarga un archivo de HDFS al sistema local."""
        try:
            self._run("-get", hdfs_path, local_path)
            logger.info("HDFS get: %s → %s", hdfs_path, local_path)
            return True
        except RuntimeError as exc:
            logger.error("get failed: %s", exc)
            return False

    def rm(self, hdfs_path: str, recursive: bool = False, skip_trash: bool = True) -> bool:
        """Elimina un archivo o directorio de HDFS."""
        args = ["-rm"]
        if recursive:
            args.append("-r")
        if skip_trash:
            args.append("-skipTrash")
        args.append(hdfs_path)
        try:
            self._run(*args)
            logger.info("HDFS rm: %s", hdfs_path)
            return True
        except RuntimeError as exc:
            logger.error("rm failed for %s: %s", hdfs_path, exc)
            return False

    def cat(self, hdfs_path: str) -> str:
        """Lee el contenido de un archivo HDFS como string."""
        result = self._run("-cat", hdfs_path)
        return result.stdout

    def count_lines(self, hdfs_path: str) -> int:
        """Cuenta líneas en un archivo HDFS."""
        content = self.cat(hdfs_path)
        return len([l for l in content.split("\n") if l.strip()])

    def disk_usage(self, hdfs_path: str) -> str:
        """Retorna uso de espacio en HDFS (human-readable)."""
        result = self._run("-du", "-s", "-h", hdfs_path, check=False)
        return result.stdout.strip()


# ===========================================================================
# Funciones de alto nivel (API pública del módulo)
# ===========================================================================

def get_hdfs_client(namenode_url: str = HDFS_URL) -> HdfsClient:
    """
    Retorna una instancia de HdfsClient configurada con las variables
    de entorno del contenedor Airflow.

    Args:
        namenode_url: URL del NameNode HDFS (default: hdfs://namenode:8020)

    Returns:
        HdfsClient listo para usar.

    Example:
        >>> client = get_hdfs_client()
        >>> client.exists("/bancomnm/input")
        True
    """
    return HdfsClient(namenode_url=namenode_url)


def upload_json_to_hdfs(
    local_path: str,
    hdfs_path: str,
    validate_json: bool = True,
    overwrite: bool = True,
) -> Dict[str, object]:
    """
    Sube un archivo JSON al HDFS con validación previa.

    Args:
        local_path: Ruta local del archivo JSON.
        hdfs_path:  Ruta destino en HDFS (incluye nombre de archivo).
        validate_json: Si True, valida la primera línea como JSON válido.
        overwrite:  Si True, sobreescribe el archivo si ya existe en HDFS.

    Returns:
        Dict con claves:
            - success (bool)
            - local_path (str)
            - hdfs_path (str)
            - size_bytes (int)
            - line_count (int)
            - error (str | None)

    Example:
        >>> result = upload_json_to_hdfs("/data/transactions.json", "/bancomnm/input/transactions.json")
        >>> print(result["success"], result["line_count"])
        True 1000000
    """
    result = {
        "success": False,
        "local_path": local_path,
        "hdfs_path": hdfs_path,
        "size_bytes": 0,
        "line_count": 0,
        "error": None,
    }

    # Verificar existencia del archivo local
    local = Path(local_path)
    if not local.exists():
        result["error"] = f"Archivo local no encontrado: {local_path}"
        logger.error(result["error"])
        return result

    result["size_bytes"] = local.stat().st_size

    # Validación de JSON (primera línea)
    if validate_json:
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if first_line:
                json.loads(first_line)
            logger.debug("JSON validation OK para %s", local_path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            result["error"] = f"Validación JSON fallida: {exc}"
            logger.error(result["error"])
            return result

    # Contar líneas
    try:
        with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
            result["line_count"] = sum(1 for _ in f)
    except OSError as exc:
        logger.warning("No se pudo contar líneas de %s: %s", local_path, exc)

    # Subir a HDFS
    client = get_hdfs_client()
    # Crear directorio padre si no existe
    parent_dir = str(Path(hdfs_path).parent)
    client.mkdir(parent_dir)

    if client.put(local_path, hdfs_path, overwrite=overwrite):
        result["success"] = True
        logger.info(
            "Upload exitoso: %s → %s (%d líneas, %.2f MB)",
            local_path,
            hdfs_path,
            result["line_count"],
            result["size_bytes"] / (1024 * 1024),
        )
    else:
        result["error"] = "Fallo al subir archivo a HDFS (ver logs hdfs)"

    return result


def read_hdfs_output(
    hdfs_path: str,
    separator: str = "\t",
    as_dict: bool = True,
) -> List:
    """
    Lee el output de un job MapReduce desde HDFS.
    Busca todos los archivos `part-*` en el directorio dado.

    Args:
        hdfs_path:  Directorio HDFS con los part-* del job.
        separator:  Separador entre clave y valor (default: tab).
        as_dict:    Si True, retorna lista de dicts {key, value}.
                    Si False, retorna lista de tuplas (key, value).

    Returns:
        Lista de registros del output MapReduce.

    Example:
        >>> records = read_hdfs_output("/bancomnm/output/job1_categoria")
        >>> for r in records[:5]:
        ...     print(r["key"], r["value"])
        compras    450230.75
        pagos      238491.00
    """
    client = get_hdfs_client()

    # Buscar todos los part-* en el directorio
    all_files = client.ls(hdfs_path)
    part_files = [f for f in all_files if "/part-" in f or f.endswith("part-00000")]

    if not part_files:
        # Intentar con glob directo
        result_glob = subprocess.run(
            [HADOOP_BIN, "dfs", "-cat", f"{hdfs_path}/part-*"],
            capture_output=True, text=True, env=_DEFAULT_ENV,
        )
        raw_content = result_glob.stdout if result_glob.returncode == 0 else ""
    else:
        raw_lines = []
        for part_file in sorted(part_files):
            content = client.cat(part_file)
            raw_lines.append(content)
        raw_content = "\n".join(raw_lines)

    records = []
    for line in raw_content.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(separator, 1)
        if len(parts) == 2:
            key, value = parts[0].strip(), parts[1].strip()
        else:
            key, value = line.strip(), ""

        if as_dict:
            records.append({"key": key, "value": value})
        else:
            records.append((key, value))

    logger.info("read_hdfs_output: %d registros leídos desde %s", len(records), hdfs_path)
    return records


def read_hdfs_output_as_stream(hdfs_path: str, separator: str = "\t") -> Iterator[tuple]:
    """
    Versión streaming de read_hdfs_output para datasets grandes.
    Genera tuplas (key, value) línea a línea para evitar cargar todo en memoria.

    Args:
        hdfs_path:  Directorio HDFS con los part-* del job.
        separator:  Separador entre clave y valor (default: tab).

    Yields:
        Tuplas (key, value) para cada línea del output.
    """
    proc = subprocess.Popen(
        [HADOOP_BIN, "dfs", "-cat", f"{hdfs_path}/part-*"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_DEFAULT_ENV,
    )

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        parts = line.split(separator, 1)
        if len(parts) == 2:
            yield parts[0].strip(), parts[1].strip()
        else:
            yield line, ""

    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ""
        logger.warning("HDFS cat terminó con rc=%d: %s", proc.returncode, err)


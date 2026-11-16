import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "5"))


def docker_get(path):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(10)
    client.connect(DOCKER_SOCKET)
    client.sendall(
        f"GET {path} HTTP/1.0\r\nHost: docker\r\nConnection: close\r\n\r\n".encode()
    )
    chunks = []
    while True:
        chunk = client.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
    client.close()
    response = b"".join(chunks)
    header, body = response.split(b"\r\n\r\n", 1)
    status = header.splitlines()[0]
    if b" 200 " not in status:
        raise RuntimeError(status.decode(errors="replace"))
    return json.loads(body)


def rate(current, previous, elapsed):
    if previous is None or elapsed <= 0 or current < previous:
        return 0.0
    return (current - previous) / elapsed


def update_metrics():
    now = time.monotonic()
    containers = docker_get("/containers/json?all=0")
    samples = {}
    for container in containers:
        container_id = container["Id"]
        names = container.get("Names", [])
        name = names[0].lstrip("/") if names else container_id[:12]
        stats = docker_get(f"/containers/{container_id}/stats?stream=false&one-shot=true")
        cpu = stats.get("cpu_stats", {})
        cpu_total = cpu.get("cpu_usage", {}).get("total_usage", 0) / 1_000_000_000
        memory = stats.get("memory_stats", {})
        usage = memory.get("usage", 0)
        cache = memory.get("stats", {}).get("cache", 0)
        working_set = max(0, usage - cache)
        network_rx = sum(v.get("rx_bytes", 0) for v in stats.get("networks", {}).values())
        network_tx = sum(v.get("tx_bytes", 0) for v in stats.get("networks", {}).values())
        details = docker_get(f"/containers/{container_id}/json?size=true")
        filesystem = details.get("SizeRw", 0) or 0
        samples[name] = {
            "container_cpu_usage_seconds_total": cpu_total,
            "container_memory_usage_bytes": usage,
            "container_memory_working_set_bytes": working_set,
            "container_network_receive_bytes_total": network_rx,
            "container_network_transmit_bytes_total": network_tx,
            "container_fs_usage_bytes": filesystem,
        }
    return now, samples


metrics_snapshot = {"timestamp": 0.0, "samples": {}, "previous": {}}


def escape_label(value):
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_metrics():
    now, samples = update_metrics()
    previous = metrics_snapshot["samples"]
    elapsed = now - metrics_snapshot["timestamp"] if metrics_snapshot["timestamp"] else 0
    lines = ["# HELP docker_exporter_up Whether the Docker Engine API can be queried.", "# TYPE docker_exporter_up gauge", "docker_exporter_up 1"]
    metric_types = {
        "container_cpu_usage_seconds_total": "counter",
        "container_memory_usage_bytes": "gauge",
        "container_memory_working_set_bytes": "gauge",
        "container_network_receive_bytes_total": "counter",
        "container_network_transmit_bytes_total": "counter",
        "container_fs_usage_bytes": "gauge",
    }
    for metric, metric_type in metric_types.items():
        lines.extend([f"# HELP {metric} Docker container {metric.removeprefix('container_').replace('_', ' ')}.", f"# TYPE {metric} {metric_type}"])
    for name, values in samples.items():
        label = escape_label(name)
        old = previous.get(name, {})
        for metric, value in values.items():
            lines.append(f'{metric}{{name="{label}"}} {value}')
    metrics_snapshot["timestamp"] = now
    metrics_snapshot["samples"] = samples
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/metrics":
            self.send_error(404)
            return
        try:
            body = render_metrics().encode()
        except Exception as exc:
            body = ("# HELP docker_exporter_up Whether Docker Engine API can be queried.\n"
                    "# TYPE docker_exporter_up gauge\ndocker_exporter_up 0\n").encode()
            print(f"metrics scrape failed: {exc}", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9101), MetricsHandler).serve_forever()

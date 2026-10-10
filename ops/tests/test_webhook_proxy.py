"""Opt-in real proxy boundary test, with synthetic payloads and no credentials."""

import http.client
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "infra/kustomize/base/platform/woodpecker-webhook"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(os.getenv("RUN_WEBHOOK_PROXY_INTEGRATION") == "1", "real Podman opt-in")
class WebhookProxy(unittest.TestCase):
    def test_request_boundary_and_exact_forwarding(self):
        received = []

        class Origin(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(
                    (
                        self.path,
                        dict(self.headers),
                        self.rfile.read(int(self.headers["Content-Length"])),
                    )
                )
                self.send_response(204)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
        thread = threading.Thread(target=origin.serve_forever, daemon=True)
        thread.start()
        hook_port, health_port = free_port(), free_port()
        config = (CONFIG / "nginx.conf").read_text()
        config = config.replace("listen 8080", f"listen {hook_port}").replace(
            "listen 8081", f"listen {health_port}"
        )
        config = config.replace(
            "woodpecker-server.woodpecker.svc.cluster.local:80", f"127.0.0.1:{origin.server_port}"
        )
        image = next(
            line.split("image: ", 1)[1].strip()
            for line in (CONFIG / "deployment.yaml").read_text().splitlines()
            if "image: " in line
        )

        def request(method, path, host="hooks.perlimen.com", body=b"", extra=None, port=None):
            connection = http.client.HTTPConnection("127.0.0.1", port or hook_port, timeout=8)
            connection.request(method, path, body=body, headers={"Host": host, **(extra or {})})
            response = connection.getresponse()
            status = response.status
            response.read()
            connection.close()
            return status

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nginx.conf"
            path.write_text(config)
            process = subprocess.Popen(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--network",
                    "host",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--tmpfs",
                    "/tmp:rw,size=64m",
                    "--volume",
                    f"{path}:/etc/nginx/nginx.conf:ro,Z",
                    "--entrypoint",
                    "nginx",
                    image,
                    "-g",
                    "daemon off;",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 15
                while True:
                    try:
                        self.assertEqual(request("GET", "/healthz", port=health_port), 200)
                        break
                    except (OSError, http.client.HTTPException):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("proxy did not become ready")
                        time.sleep(0.1)
                body = b'{"synthetic":"\xc5\xbbaba","bytes":"raw"}\n'
                headers = {
                    "X-Hub-Signature-256": "sha256=synthetic",
                    "X-GitHub-Event": "ping",
                    "X-GitHub-Delivery": "synthetic-delivery",
                    "Content-Type": "application/json",
                }
                query = "/api/hook?access_token=synthetic-query&literal=%2B%2F"
                self.assertEqual(request("POST", query, body=body, extra=headers), 204)
                self.assertEqual(len(received), 1)
                self.assertEqual(received[0][0], query)
                self.assertEqual(received[0][2], body)
                for key, value in headers.items():
                    self.assertEqual(received[0][1][key], value)
                methods = ["GET", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"]
                for method in methods:
                    self.assertEqual(request(method, query), 405)
                paths = [
                    "/",
                    "/api/user",
                    "/authorize",
                    "/metrics",
                    "/healthz",
                    "/api/hook/",
                    "/api//hook",
                    "/api/%68ook",
                    "/api/hook%3F",
                    "/x/../api/hook",
                ]
                for route in paths:
                    self.assertEqual(request("POST", route), 404, route)
                self.assertEqual(request("POST", query, host="woodpecker.internal"), 404)
                self.assertEqual(len(received), 1)
                print(
                    json.dumps(
                        {
                            "exactBodyQueryHeaders": True,
                            "rejectedMethods": len(methods),
                            "rejectedPaths": len(paths),
                            "wrongHostRejected": True,
                        }
                    )
                )
            finally:
                process.terminate()
                logs, _ = process.communicate(timeout=10)
                if process.returncode not in (0, -15):
                    print(logs.decode(errors="replace"))
                origin.shutdown()
                origin.server_close()
                self.assertNotIn(b"synthetic-query", logs)
                self.assertNotIn(b"synthetic-delivery", logs)

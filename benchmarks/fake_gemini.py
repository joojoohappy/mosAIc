"""A local stand-in for the Gemini Interactions endpoint, for benchmarks only.

It speaks the response shape apps/backend/app/provider.py parses
({"output_image": {"data": <base64>}}) and can be told to misbehave. Every
number measured against it is the cost of MOSAIC's own code plus a simulated
delay. It says nothing about real Gemini latency, quality or price.

Modes (set with POST /__mode {"mode": ..., "delay": seconds}):
    ok      wait `delay`, then return a valid PNG
    error   HTTP 500 with a JSON error body
    hang    wait `delay`, then return a valid PNG (use a delay past the timeout)
    drip    send headers at once, then the body one byte every `delay` seconds
            (a stalled upstream that never trips a per-read socket timeout)
    text    HTTP 200 with a text-only answer (e.g. a safety refusal)
    badjson HTTP 200 with a body that is not JSON

GET /__stats returns {"calls": n}; POST /__reset zeroes it.
"""

from __future__ import annotations

import base64
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# A real 1x1 PNG, the same bytes the backend unit tests use.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
OK_BODY = json.dumps({"output_image": {"data": base64.b64encode(PNG).decode()}}).encode()

state = {"mode": "ok", "delay": 0.0, "calls": 0}
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep benchmark output clean
        pass

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/__stats":
            with lock:
                return self._json(200, {"calls": state["calls"]})
        self._json(404, {})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        if self.path == "/__mode":
            cfg = json.loads(raw or b"{}")
            with lock:
                state["mode"] = cfg.get("mode", "ok")
                state["delay"] = float(cfg.get("delay", 0))
            return self._json(200, state)
        if self.path == "/__reset":
            with lock:
                state["calls"] = 0
            return self._json(200, state)

        with lock:
            state["calls"] += 1
            mode, delay = state["mode"], state["delay"]

        if mode == "error":
            return self._json(500, {"error": {"message": "upstream exploded"}})
        if mode == "text":
            return self._json(200, {"steps": [{"content": [{"type": "text", "text": "I can't help with that."}]}]})
        if mode == "badjson":
            self.send_response(200)
            self.send_header("Content-Length", "9")
            self.end_headers()
            self.wfile.write(b"<html>oops")
            return None
        if mode == "drip":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(OK_BODY)))
            self.end_headers()
            try:
                for b in OK_BODY:
                    self.wfile.write(bytes([b]))
                    self.wfile.flush()
                    time.sleep(delay)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return None
        # ok / hang
        time.sleep(delay)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(OK_BODY)))
            self.end_headers()
            self.wfile.write(OK_BODY)
        except (BrokenPipeError, ConnectionResetError):
            pass
        return None


def serve(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    srv = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8790)
    print(f"fake gemini on http://127.0.0.1:{srv.server_address[1]}/v1beta/interactions")
    threading.Event().wait()

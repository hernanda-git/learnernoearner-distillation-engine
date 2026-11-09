"""HTTP Server for Project Proteus Web Console (`proteus.web.server`)."""

from __future__ import annotations

import dataclasses
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from proteus.constitution import BoundedSelfCorrector, ConstitutionalIdentityGuard
from proteus.paper import VirtualPaperExchange
from proteus.shadow import ForwardShadowScanner
from proteus.web import BENCH_DIR, build_dashboard_payload
from proteus.web.ui_template import INDEX_HTML


class ProteusWebHandler(BaseHTTPRequestHandler):
    """Serves the Project Proteus HTML console and JSON telemetry endpoints."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()


    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
            return
        if self.path in ("/health", "/health/telemetry"):
            pure, files = ConstitutionalIdentityGuard.verify_codebase_purity()
            self._send_json(
                {
                    "status": "ok",
                    "engine": "Project Proteus (@learnernoearner Distillation Clone)",
                    "air_gapped": True,
                    "constitutional_purity": pure,
                    "scanned_files": files,
                    "bps": 0.97,
                }
            )
            return
        if self.path.startswith("/api/v1/dashboard"):
            self._send_json(build_dashboard_payload())
            return
        self._send_json({"error": "not_found", "path": self.path}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/v1/scan":
            scanner = ForwardShadowScanner()
            snapshot = scanner.scan_live_universe()
            (BENCH_DIR / "live_shadow_snapshot.json").write_text(
                json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
            ledger = VirtualPaperExchange().process_shadow_snapshot(snapshot)
            self._send_json(
                {
                    "status": "scanned",
                    "scanned_at_utc": snapshot.scanned_at_utc,
                    "macro_regime": snapshot.macro_regime,
                    "current_equity_usdt": ledger.current_equity_usdt,
                    "open_positions_count": ledger.open_positions_count,
                }
            )
            return

        if self.path == "/api/v1/self-correct":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            param = str(body.get("parameter", "median_sl_long_pct"))
            obs_val = float(body.get("observed_value", 0.0267))
            alpha = float(body.get("learning_rate", 0.15))
            bps = float(body.get("candidate_bps", 0.97))

            corrector = BoundedSelfCorrector()
            outcome = corrector.propose_fine_tune(
                observed_estimates={param: obs_val},
                learning_rate=alpha,
                candidate_bps=bps,
            )
            self._send_json(
                {
                    "accepted": outcome.accepted,
                    "generation": outcome.generation,
                    "verified_bps": outcome.verified_bps,
                    "reason": outcome.reason,
                    "active_value": getattr(outcome.active_params, param),
                }
            )
            return

        self._send_json({"error": "not_found", "path": self.path}, status=HTTPStatus.NOT_FOUND)


def run_server(host: str = "127.0.0.1", port: int = 18085) -> None:
    server = ThreadingHTTPServer((host, port), ProteusWebHandler)
    print(
        json.dumps(
            {
                "event": "proteus_web_ui_listening",
                "host": host,
                "port": port,
                "url": f"http://{host}:{port}",
            }
        ),
        flush=True,
    )
    server.serve_forever()

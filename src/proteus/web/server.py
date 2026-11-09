"""HTTP Server for Project Proteus Web Console (`proteus.web.server`)."""

from __future__ import annotations

import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from proteus.constitution import BoundedSelfCorrector, ConstitutionalIdentityGuard
from proteus.evolver import AgenticSelfImprover
from proteus.monitor import SelfMonitoringWatchdog
from proteus.paper import VirtualPaperExchange
from proteus.replay import EmpiricalCorpusReplay
from proteus.shadow import ForwardShadowScanner
from proteus.web import BENCH_DIR, build_dashboard_payload
from proteus.web.ui_template import INDEX_HTML

_HEALTH_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_DASHBOARD_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_CACHE_TTL_SECONDS = 30.0


class ProteusWebHandler(BaseHTTPRequestHandler):
    """Serves the Project Proteus HTML console and JSON telemetry endpoints."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _post_authorized(self) -> bool:
        """Require a token when configured, otherwise require the same-origin CSRF header."""
        token = os.getenv("PROTEUS_API_TOKEN", "")
        if token:
            return self.headers.get("X-Proteus-Token") == token
        return self.headers.get("X-Proteus-Action") == "1"

    @staticmethod
    def _health_payload() -> dict[str, Any]:
        now = time.monotonic()
        cached = _HEALTH_CACHE["payload"]
        if cached is not None and now - _HEALTH_CACHE["at"] < _CACHE_TTL_SECONDS:
            return cached

        pure, files = ConstitutionalIdentityGuard.verify_codebase_purity()
        mon = SelfMonitoringWatchdog().evaluate_and_heal()
        parity = EmpiricalCorpusReplay().run().parity_metrics
        payload = {
            "status": "ok",
            "engine": "Project Proteus (@learnernoearner Distillation Clone)",
            "air_gapped": True,
            "constitutional_purity": pure,
            "scanned_files": files,
            "self_monitor_status": mon.overall_status,
            "bps": parity.bps,
            "validated": parity.passed,
            "unmeasured": list(parity.unmeasured),
        }
        _HEALTH_CACHE["at"] = now
        _HEALTH_CACHE["payload"] = payload
        return payload

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
            self._send_json(self._health_payload())
            return
        if self.path.startswith("/api/v1/dashboard"):
            refresh = "refresh=1" in self.path
            now = time.monotonic()
            cached = _DASHBOARD_CACHE["payload"]
            if not refresh and cached is not None and now - _DASHBOARD_CACHE["at"] < _CACHE_TTL_SECONDS:
                self._send_json(cached)
                return
            payload = build_dashboard_payload()
            _DASHBOARD_CACHE["at"] = now
            _DASHBOARD_CACHE["payload"] = payload
            self._send_json(payload)
            return
        self._send_json({"error": "not_found", "path": self.path}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self._post_authorized():
            self._send_json(
                {"error": "forbidden", "detail": "Missing X-Proteus-Token or X-Proteus-Action header."},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        if self.path == "/api/v1/scan":
            scanner = ForwardShadowScanner()
            snapshot = scanner.scan_live_universe()
            (BENCH_DIR / "live_shadow_snapshot.json").write_text(
                json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
            ledger = VirtualPaperExchange().process_shadow_snapshot(snapshot)
            mon = SelfMonitoringWatchdog().evaluate_and_heal()
            self._send_json(
                {
                    "status": "scanned",
                    "scanned_at_utc": snapshot.scanned_at_utc,
                    "macro_regime": snapshot.macro_regime,
                    "current_equity_usdt": ledger.current_equity_usdt,
                    "open_positions_count": ledger.open_positions_count,
                    "self_monitor_status": mon.overall_status,
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

        if self.path == "/api/v1/evolve":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            alpha = float(body.get("learning_rate", 0.12))
            improver = AgenticSelfImprover()
            entry = improver.run_improvement_cycle(
                trigger_source="web_ui_manual_trigger",
                learning_rate=alpha,
            )
            valid, chain_len = improver.verify_journal_hash_chain()
            self._send_json(
                {
                    "entry": entry.to_dict(),
                    "hash_chain_valid": valid,
                    "journal_length": chain_len,
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

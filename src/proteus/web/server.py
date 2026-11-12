"""HTTP Server for Project Proteus Web Console (`proteus.web.server`).

Security model:
- Every state-changing ``POST`` requires ``X-Proteus-Action: 1`` and, when
  ``PROTEUS_API_TOKEN`` is configured, a matching ``X-Proteus-Token``.
- If no token is configured, POSTs are accepted only from a direct loopback
  client that did not arrive through a reverse proxy (no ``X-Forwarded-For``).
  OpenLiteSpeed always adds the forwarded header, so a public deployment cannot
  fall back to the loopback rule.
- ``/health`` and cached dashboard reads are side-effect free. Expensive
  refreshes and all POSTs are rate-limited per client.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from proteus.constitution import BoundedSelfCorrector, ConstitutionalIdentityGuard
from proteus.evolver import AgenticSelfImprover
from proteus.monitor import SelfMonitoringWatchdog
from proteus.paper import VirtualPaperExchange
from proteus.paths import state_path
from proteus.replay import EmpiricalCorpusReplay
from proteus.shadow import ForwardShadowScanner
from proteus.web import build_dashboard_payload
from proteus.web.ui_template import INDEX_HTML

_HEALTH_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_DASHBOARD_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_CACHE_TTL_SECONDS = 30.0
_MAX_BODY_BYTES = 65536
_LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}

_RATE_LOCK = threading.Lock()
_RATE_HITS: dict[tuple[str, str], list[float]] = {}


def is_post_authorized(
    client_ip: str,
    headers: Mapping[str, str],
    token: str,
) -> bool:
    """Return whether a POST may mutate server state."""
    if headers.get("X-Proteus-Action") != "1":
        return False
    if token:
        return hmac.compare_digest(headers.get("X-Proteus-Token", ""), token)
    forwarded = headers.get("X-Forwarded-For") or headers.get("X-Real-IP")
    return forwarded is None and client_ip in _LOOPBACK


def _allow_request(client_ip: str, endpoint: str, limit: int, window_seconds: float) -> bool:
    """Per-client sliding-window rate limit."""
    now = time.monotonic()
    key = (client_ip, endpoint)
    with _RATE_LOCK:
        hits = [stamp for stamp in _RATE_HITS.get(key, []) if now - stamp < window_seconds]
        if len(hits) >= limit:
            _RATE_HITS[key] = hits
            return False
        hits.append(now)
        _RATE_HITS[key] = hits
        return True


class ProteusWebHandler(BaseHTTPRequestHandler):
    """Serves the Project Proteus HTML console and JSON telemetry endpoints."""

    def log_message(self, format: str, *args: object) -> None:
        return

    def _client_ip(self) -> str:
        return str(self.client_address[0])

    def _post_authorized(self) -> bool:
        return is_post_authorized(
            self._client_ip(),
            self.headers,
            os.getenv("PROTEUS_API_TOKEN", ""),
        )

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > _MAX_BODY_BYTES:
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _health_payload() -> dict[str, Any]:
        now = time.monotonic()
        cached = _HEALTH_CACHE["payload"]
        if cached is not None and now - _HEALTH_CACHE["at"] < _CACHE_TTL_SECONDS:
            return cached

        pure, files = ConstitutionalIdentityGuard.verify_codebase_purity()
        mon = SelfMonitoringWatchdog().evaluate_and_heal(persist=False)
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
            "auth_required": bool(os.getenv("PROTEUS_API_TOKEN", "")),
        }
        _HEALTH_CACHE["at"] = now
        _HEALTH_CACHE["payload"] = payload
        return payload

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_HEAD(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
            return
        if self.path in ("/health", "/health/telemetry"):
            self._send_json(self._health_payload())
            return
        if self.path.startswith("/api/v1/dashboard"):
            refresh = "refresh=1" in self.path
            if refresh:
                if not self._post_authorized():
                    self._send_json(
                        {"error": "unauthorized", "detail": "refresh=1 requires API authorization."},
                        status=HTTPStatus.UNAUTHORIZED,
                    )
                    return
                if not _allow_request(self._client_ip(), "dashboard_refresh", 6, 60.0):
                    self._send_json(
                        {"error": "rate_limited", "detail": "Max 6 dashboard refreshes/minute."},
                        status=HTTPStatus.TOO_MANY_REQUESTS,
                    )
                    return
            now = time.monotonic()
            cached = _DASHBOARD_CACHE["payload"]
            if not refresh and cached is not None and now - _DASHBOARD_CACHE["at"] < _CACHE_TTL_SECONDS:
                self._send_json(cached)
                return
            payload = build_dashboard_payload(persist=False)
            _DASHBOARD_CACHE["at"] = now
            _DASHBOARD_CACHE["payload"] = payload
            self._send_json(payload)
            return
        self._send_json({"error": "not_found", "path": self.path}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._post_authorized():
            self._send_json(
                {
                    "error": "unauthorized",
                    "detail": "Valid X-Proteus-Action and X-Proteus-Token headers are required.",
                },
                status=HTTPStatus.UNAUTHORIZED,
            )
            return

        if self.path == "/api/v1/scan":
            if not _allow_request(self._client_ip(), "scan", 6, 60.0):
                self._send_json(
                    {"error": "rate_limited", "detail": "Max 6 scans/minute."},
                    status=HTTPStatus.TOO_MANY_REQUESTS,
                )
                return
            scanner = ForwardShadowScanner()
            snapshot = scanner.scan_live_universe()
            state_path("live_shadow_snapshot.json", seed=False).write_text(
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
            if not _allow_request(self._client_ip(), "self_correct", 10, 60.0):
                self._send_json(
                    {"error": "rate_limited", "detail": "Max 10 corrections/minute."},
                    status=HTTPStatus.TOO_MANY_REQUESTS,
                )
                return
            body = self._read_json_body()
            if body is None:
                self._send_json(
                    {"error": "bad_request", "detail": "A JSON object body is required."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            measured_bps = EmpiricalCorpusReplay().run().parity_metrics.bps
            if measured_bps is None:
                self._send_json(
                    {
                        "error": "unvalidated",
                        "detail": "BPS is unmeasured; parameter updates are refused.",
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            try:
                param = str(body.get("parameter", "median_sl_long_pct"))
                observed_value = float(body["observed_value"])
                learning_rate = float(body.get("learning_rate", 0.15))
            except (KeyError, TypeError, ValueError):
                self._send_json(
                    {"error": "bad_request", "detail": "parameter/observed_value/learning_rate are required."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            outcome = BoundedSelfCorrector().propose_fine_tune(
                observed_estimates={param: observed_value},
                learning_rate=learning_rate,
                candidate_bps=measured_bps,
            )
            self._send_json(
                {
                    "accepted": outcome.accepted,
                    "generation": outcome.generation,
                    "verified_bps": outcome.verified_bps,
                    "reason": outcome.reason,
                    "active_value": getattr(outcome.active_params, param, None),
                }
            )
            return

        if self.path == "/api/v1/evolve":
            if not _allow_request(self._client_ip(), "evolve", 2, 3600.0):
                self._send_json(
                    {"error": "rate_limited", "detail": "Max 2 evolution cycles/hour."},
                    status=HTTPStatus.TOO_MANY_REQUESTS,
                )
                return
            body = self._read_json_body() or {}
            try:
                alpha = float(body.get("learning_rate", 0.12))
            except (TypeError, ValueError):
                alpha = 0.12
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
    if host not in _LOOPBACK and not os.getenv("PROTEUS_API_TOKEN", ""):
        raise SystemExit("Refusing to bind a non-loopback interface without PROTEUS_API_TOKEN.")
    server = ThreadingHTTPServer((host, port), ProteusWebHandler)
    print(
        json.dumps(
            {
                "event": "proteus_web_ui_listening",
                "host": host,
                "port": port,
                "url": f"http://{host}:{port}",
                "auth_required": bool(os.getenv("PROTEUS_API_TOKEN", "")),
            }
        ),
        flush=True,
    )
    server.serve_forever()

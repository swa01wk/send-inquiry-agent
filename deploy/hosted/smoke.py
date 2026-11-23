"""Smoke test for the hosted POC (deploy/hosted), run by CI against the real stack.

Standard library only, so it runs on any CI runner or VM:

    python3 deploy/hosted/smoke.py https://localhost ci <password> --save-session /tmp/sid
    docker compose -f deploy/hosted/docker-compose.yml restart backend
    python3 deploy/hosted/smoke.py https://localhost ci <password> --check-session /tmp/sid

It checks: the password covers the pages and /api (including /dev); the built app and
its client routes are served; /api/health answers; a chat turn streams through Caddy
(scripted model, scenario 03-no-cr); and a session survives a backend restart (Postgres).
"""

from __future__ import annotations

import argparse
import base64
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# CI uses Caddy's internal CA for "localhost"; a real VM has a Let's Encrypt certificate.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_failures: list[str] = []


def _check(ok: bool, what: str) -> None:
    print(("PASS " if ok else "FAIL ") + what)
    if not ok:
        _failures.append(what)


def _request(
    base: str,
    path: str,
    auth: str | None,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(base + path, method=method)
    if auth:
        req.add_header("Authorization", "Basic " + auth)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, context=_CTX, timeout=60) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def _wait_until_up(base: str, auth: str) -> None:
    for _ in range(60):
        try:
            status, _, _ = _request(base, "/api/health", auth)
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(2)
    _check(False, "the stack answers /api/health within 2 minutes")


def run_checks(base: str, auth: str, save_session: Path | None) -> None:
    _wait_until_up(base, auth)

    # The password covers everything, /api and /dev included.
    for path in ("/", "/api/health", "/api/dev/outbox", "/review"):
        status, headers, _ = _request(base, path, None)
        _check(
            status == 401 and "basic" in headers.get("Www-Authenticate", "").lower(),
            f"{path} without the password → 401 with a login prompt",
        )
    status, _, _ = _request(base, "/", "Y2k6d3Jvbmc=")  # ci:wrong
    _check(status == 401, "a wrong password → 401")

    # The built app and its client-side routes.
    status, headers, page = _request(base, "/", auth)
    _check(status == 200 and b'id="root"' in page, "/ serves the built app")
    status, _, page = _request(base, "/review", auth)
    _check(
        status == 200 and b'id="root"' in page,
        "a client route (/review) serves the app",
    )
    status, headers, _ = _request(base, "/", auth)
    _check(
        "max-age" in headers.get("Strict-Transport-Security", ""), "HSTS header is set"
    )

    # The API through Caddy.
    status, _, body = _request(base, "/api/health", auth)
    _check(status == 200 and json.loads(body).get("status") == "ok", "/api/health → ok")

    # A chat turn streams through the proxy (scripted model: no key needed in CI).
    status, _, body = _request(
        base,
        "/api/sessions",
        auth,
        method="POST",
        body={},
        headers={"X-Test-Scenario": "03-no-cr"},
    )
    _check(status == 200, "POST /api/sessions → 200")
    if status != 200:
        return
    session_id = json.loads(body)["session_id"]
    status, headers, stream = _request(
        base,
        f"/api/sessions/{session_id}/chat",
        auth,
        method="POST",
        body={"type": "message", "text": "What's a CR number?"},
    )
    text = stream.decode(errors="replace")
    _check(
        status == 200
        and headers.get("Content-Type", "").startswith("text/event-stream"),
        "chat answers as a server-sent event stream",
    )
    _check(
        "event: token" in text or "event: ui_card" in text, "the stream carries a reply"
    )
    _check("event: done" in text, "the stream ends with done")
    if save_session:
        save_session.write_text(session_id, encoding="utf-8")


def check_session(base: str, auth: str, session_file: Path) -> None:
    _wait_until_up(base, auth)
    session_id = session_file.read_text(encoding="utf-8").strip()
    status, _, _ = _request(base, f"/api/sessions/{session_id}/draft", auth)
    _check(status == 200, "the session survives a backend restart (Postgres)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="e.g. https://localhost")
    parser.add_argument("user")
    parser.add_argument("password")
    parser.add_argument("--save-session", type=Path)
    parser.add_argument("--check-session", type=Path)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    auth = base64.b64encode(f"{args.user}:{args.password}".encode()).decode()
    if args.check_session:
        check_session(base, auth, args.check_session)
    else:
        run_checks(base, auth, args.save_session)
    if _failures:
        print(f"\n{len(_failures)} check(s) failed", file=sys.stderr)
        return 1
    print("\nAll checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

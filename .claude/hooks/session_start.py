#!/usr/bin/env python3
"""Contra SessionStart probe for Claude Code on the web (Dispatch).

Runs once at the start of each Dispatched cloud session and reports, in a few
clear lines, whether the environment can actually run the `by` series in
key-free delegation mode:

  1. The interpreter `.mcp.json` launches the MCP server with (`python`) exists
     and is 3.10+ (the contra package targets 3.10+; deps are standard-library
     -centric). On Ubuntu cloud hosts `python` is frequently absent while
     `python3` is present, so we check and flag that mismatch explicitly.
  2. api.openalex.org is reachable. Contra builds the bybridge pool from
     OpenAlex near-field seeds, so if egress to that host is blocked the whole
     `by` flow stalls at 0 candidates. We probe it EXACTLY ONCE — no retry, no
     fallback host — and report the result so the operator can open the domain
     in the environment's Network access policy (which can only be changed in
     the web UI, not from code).

Output: a short plain-text report to stdout (Claude Code injects a SessionStart
hook's stdout into the session context). The probe never blocks the session —
it always exits 0. Its job is to report, not to gate.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.error
import urllib.request

OPENALEX_PROBE_URL = "https://api.openalex.org/works?per_page=1"
PROBE_TIMEOUT_SEC = 10
BLOCKED_MSG = (
    "OpenAlex egress blocked — allow api.openalex.org in this environment's "
    "Network access (Custom)"
)


def _version_of(cmd: str):
    """Return (major, minor, micro) for an interpreter command, or None."""
    if not shutil.which(cmd):
        return None
    try:
        out = subprocess.run(
            [cmd, "-c", "import sys;print('%d %d %d' % sys.version_info[:3])"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    parts = (out.stdout or "").split()
    if len(parts) != 3:
        return None
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _check_python() -> str:
    """Verify the `python` command (.mcp.json's launcher) is present and >=3.10.

    If `python` is missing but `python3` works (common on Ubuntu cloud hosts),
    say so plainly so the operator can switch .mcp.json's command to python3.
    """
    py = _version_of("python")
    if py and py >= (3, 10):
        return f"Python {py[0]}.{py[1]}.{py[2]} OK (>=3.10, `python` command)"
    if py:
        return f"`python` is {py[0]}.{py[1]}.{py[2]} — contra requires Python 3.10+"
    py3 = _version_of("python3")
    if py3 and py3 >= (3, 10):
        return (
            f"`python` not found, but python3 is {py3[0]}.{py3[1]}.{py3[2]} — "
            "set .mcp.json command to python3"
        )
    if py3:
        return (
            f"`python` not found; python3 is {py3[0]}.{py3[1]}.{py3[2]} "
            "(< 3.10) — install Python 3.10+"
        )
    return "no python/python3 interpreter found — install Python 3.10+"


def _probe_openalex() -> str:
    """Single reachability probe. No retry, no bypass (per egress policy)."""
    req = urllib.request.Request(
        OPENALEX_PROBE_URL, headers={"User-Agent": "contra-session-probe/0.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_SEC) as res:
            status = getattr(res, "status", res.getcode())
            if status and 200 <= status < 300:
                return "OpenAlex reachable"
            return BLOCKED_MSG
    except urllib.error.HTTPError:
        # 403 (egress policy) or any other HTTP status -> treat as blocked.
        return BLOCKED_MSG
    except Exception:
        # DNS failure, timeout, connection refused, TLS error, etc.
        return BLOCKED_MSG


def main() -> int:
    lines = [
        "contra Dispatch session check:",
        f"- {_check_python()}",
        f"- {_probe_openalex()}",
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

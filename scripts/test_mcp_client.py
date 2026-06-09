"""Automated mock client to test the stdio JSON-RPC MCP Server."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Any, Dict, Optional


def _log(msg: str) -> None:
    print(f"[mcp-client-test] {msg}")


def send_message(proc: subprocess.Popen, payload: Dict[str, Any]) -> None:
    msg = json.dumps(payload, ensure_ascii=False) + "\n"
    proc.stdin.write(msg)
    proc.stdin.flush()
    _log(f"Sent: {method_label(payload)}")


def read_message(proc: subprocess.Popen, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    # Simple poll-based read line with timeout
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if line:
            payload = json.loads(line.strip())
            _log(f"Received: {method_label(payload)}")
            return payload
        time.sleep(0.1)
    return None


def method_label(payload: Dict[str, Any]) -> str:
    if "method" in payload:
        return f"Method={payload['method']} (id={payload.get('id')})"
    if "result" in payload:
        return f"Result (id={payload.get('id')})"
    if "error" in payload:
        return f"Error: {payload['error'].get('message')} (id={payload.get('id')})"
    return str(payload)


def run_tests() -> int:
    _log("Starting MCP Server process...")
    # Start server in unbuffered mode
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "src.cli.main", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )

    try:
        # 1. Send initialize handshake
        init_id = 1
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        })
        
        resp = read_message(proc)
        assert resp is not None, "No response to initialize request"
        assert resp.get("id") == init_id, f"Invalid ID in initialize response: {resp}"
        assert "result" in resp, f"Initialize response has no result: {resp}"
        _log("Initialize handshake response verified.")

        # 2. Send initialized notification
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        # Note: initialized notifications don't get a response.
        _log("Initialized notification sent.")

        # 3. Request tools list
        list_id = 2
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": list_id,
            "method": "tools/list"
        })
        
        resp = read_message(proc)
        assert resp is not None, "No response to tools/list request"
        assert resp.get("id") == list_id, f"Invalid ID in tools/list response: {resp}"
        assert "result" in resp, f"tools/list response has no result: {resp}"
        tools = resp["result"].get("tools", [])
        tool_names = [t.get("name") for t in tools]
        _log(f"Discovered tools: {tool_names}")
        assert "byserendipity_discover" in tool_names, "Missing byserendipity_discover tool"
        assert "byrepo_search" in tool_names, "Missing byrepo_search tool"
        assert "bynote_link_concepts" in tool_names, "Missing bynote_link_concepts tool"
        _log("Tools list verified successfully.")

        # 4. Test bynote_link_concepts tool execution
        call_id = 3
        _log("Calling bynote_link_concepts tool...")
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": "bynote_link_concepts",
                "arguments": {
                    "note_content": "We need to build a distributed cache that handles network splits by dynamically sacrificing consistency for availability (AP system) using Hashed-Trie rings.",
                    "theme_overview": "Distributed consensus and partition tolerance in Edge databases."
                }
            }
        })
        
        # Give LLM request a bit of time (up to 30 seconds)
        resp = read_message(proc, timeout=30.0)
        assert resp is not None, "No response to tool call"
        assert resp.get("id") == call_id, f"Invalid ID in tool call response: {resp}"
        assert "result" in resp, f"Tool call response has no result: {resp}"
        result = resp["result"]
        assert result.get("isError") is False, f"Tool execution error: {result.get('content')}"
        content = result.get("content", [])
        assert len(content) > 0, "Empty content returned from tool call"
        text = content[0].get("text", "")
        _log(f"Tool execution succeeded. Output snippet:\n---\n{text[:300]}...\n---")

        _log("All MCP server tests passed successfully!")
        return 0

    except AssertionError as e:
        _log(f"Test Assertion Failed: {e}")
        # Print stderr from server for diagnostics
        proc.terminate()
        stderr_log = proc.stderr.read()
        if stderr_log:
            _log(f"Server Stderr Logs:\n{stderr_log}")
        return 1
    except Exception as e:
        _log(f"Unexpected Test Error: {e}")
        return 1
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    sys.exit(run_tests())

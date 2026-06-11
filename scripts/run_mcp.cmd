@echo off
rem Stdio MCP server launcher for the contra "by" series (byrepo, byserendipity, bynote).
rem The server imports src.* and resolves data paths relative to the repo root, so cd first.
cd /d D:\dev\repos\contra
python -u -m src.cli.main --mcp

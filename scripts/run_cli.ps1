# Phase 1 CLI runner (template)
# Usage: .\scripts\run_cli.ps1 -Input theme.json -Out output\

param(
  [Parameter(Mandatory=$true)]
  [string]$Input,

  [Parameter(Mandatory=$true)]
  [string]$Out
)

python -m src.cli.main --input $Input --out $Out

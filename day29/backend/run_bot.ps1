$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Starting Day 28 RAG bot (local LLM)..." -ForegroundColor Cyan
& "$PSScriptRoot\.venv\Scripts\python.exe" -m app.main

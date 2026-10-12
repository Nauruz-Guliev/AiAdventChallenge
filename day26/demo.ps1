# ============================================================
#  День 26 — Запуск локальной LLM (Ollama + gemma4:12b)
#  Проверка: модель запускается локально, доступна по HTTP API,
#  отвечает на запросы разной сложности.
# ============================================================

$Model   = "gemma4:12b"
$ApiBase = "http://localhost:11434"

# ---------- 0. Проверка, что Ollama и модель на месте ----------
Write-Output "===== Ollama version ====="
ollama --version
Write-Output "`n===== Installed models ====="
ollama list

# ---------- 1. Модель доступна по HTTP API ----------
Write-Output "`n===== HTTP API health ====="
Invoke-RestMethod -Uri "$ApiBase/api/version" | ConvertTo-Json -Compress

# ---------- 2. Три запроса разной сложности ----------
$prompts = @(
    @{ Level = "SIMPLE"; Text = "Hi! What is your name and what can you do?" },
    @{ Level = "MEDIUM"; Text = "Explain in 2-3 sentences: what is the difference between a process and a thread?" },
    @{ Level = "HARD";   Text = "Write a Python function that checks whether a string is a palindrome, ignoring case and non-alphanumeric characters. Then briefly explain its time and space complexity." }
)

foreach ($p in $prompts) {
    $body = @{
        model  = $Model
        prompt = $p.Text
        stream = $false
    } | ConvertTo-Json

    Write-Output "`n==================== REQUEST ($($p.Level)) ===================="
    $r = Invoke-RestMethod -Uri "$ApiBase/api/generate" `
                           -Method Post `
                           -Body $body `
                           -ContentType "application/json"
    Write-Output $r.response
}

Write-Output "`n==================== DONE ===================="

# ---------- Альтернатива: CLI вместо HTTP API ----------
# ollama run gemma4:12b "Hi! What is your name?"

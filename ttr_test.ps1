# Failure injection + TTR measurement (Windows PowerShell version)
# Run:  powershell -ExecutionPolicy Bypass -File .\ttr_test.ps1
param(
    [string]$Base = "http://localhost:5000",
    [string]$Container = "dynamic-qr"
)

function Test-Health {
    try {
        $r = Invoke-WebRequest -Uri "$Base/health" -UseBasicParsing -TimeoutSec 1
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

Write-Host "[1] Before failure: checking health..."
if (-not (Test-Health)) {
    Write-Host "Service healthy nahi hai. Pehle 'docker compose up --build -d' chalao."
    exit 1
}
Write-Host "    OK"

Write-Host "[2] Injecting failure: crashing the app process inside container '$Container'"
# 'docker kill' ko Docker manual stop maanta hai (restart policy kaam nahi karti).
# Isliye container ke andar ka main process (PID 1 = gunicorn) band karte hain.
# Process marne par container exit hota hai aur restart policy ('always') use wapas uthati hai.
$sw = [System.Diagnostics.Stopwatch]::StartNew()
docker exec $Container python -c "import os, signal; os.kill(1, signal.SIGTERM)" | Out-Null

Write-Host "[3] Waiting for detection (health check fails)..."
$limit = 60
while ((Test-Health) -and ($sw.Elapsed.TotalSeconds -lt $limit)) { Start-Sleep -Milliseconds 100 }
$tDetect = $sw.Elapsed.TotalSeconds

Write-Host "[4] Waiting for recovery (Docker restart policy)..."
while ((-not (Test-Health)) -and ($sw.Elapsed.TotalSeconds -lt 120)) { Start-Sleep -Milliseconds 200 }
$tRecover = $sw.Elapsed.TotalSeconds
if (-not (Test-Health)) {
    Write-Host "Service wapas nahi aayi (120 s timeout). 'docker ps -a' check karo."
    exit 1
}

Write-Host "[5] Verification: health + create + redirect"
$body = '{"url":"https://example.com"}'
$resp = Invoke-RestMethod -Uri "$Base/api/create" -Method Post -ContentType "application/json" -Body $body
# curl.exe Windows 10/11 me built-in hota hai; redirect follow nahi karta, sirf status code deta hai.
$status = (curl.exe -s -o NUL -m 3 -w "%{http_code}" "$Base/r/$($resp.code)")
Write-Host "    redirect status: $status (302 aana chahiye)"
$tVerify = $sw.Elapsed.TotalSeconds
$sw.Stop()

"{0,-16}: {1:N2} s" -f "Detection time", $tDetect
"{0,-16}: {1:N2} s" -f "Recovery time", ($tRecover - $tDetect)
"{0,-16}: {1:N2} s" -f "Verification", ($tVerify - $tRecover)
"{0,-16}: {1:N2} s" -f "TTR (total)", $tVerify

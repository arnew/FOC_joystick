# ============================================================================
# Complete PlatformIO Environment Deployment Test Script
# ============================================================================
# Tests all environment transitions including idempotent deployments

$ErrorActionPreference = "Stop"
$deployments = @()
$pioPath = "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe"

function Deploy-Environment {
    param(
        [string]$env,
        [string]$description
    )
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Deployment #$($deployments.Count + 1): $description" -ForegroundColor Cyan
    Write-Host "Environment: $env" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    $startTime = Get-Date
    
    try {
        & $pioPath run --target upload --environment $env
        $exitCode = $LASTEXITCODE
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalSeconds
        
        if ($exitCode -eq 0) {
            Write-Host ""
            Write-Host "SUCCESS" -ForegroundColor Green
            $status = "SUCCESS"
        } else {
            Write-Host ""
            Write-Host "FAILED (Exit Code: $exitCode)" -ForegroundColor Red
            $status = "FAILED"
        }
    } catch {
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalSeconds
        Write-Host ""
        Write-Host "ERROR: $_" -ForegroundColor Red
        $status = "ERROR"
        $exitCode = -1
    }
    
    $deployments += [PSCustomObject]@{
        Number = $deployments.Count + 1
        Environment = $env
        Description = $description
        Status = $status
        ExitCode = $exitCode
        Duration = [math]::Round($duration, 2)
        Timestamp = $startTime
    }
}

Write-Host "============================================================================" -ForegroundColor Yellow
Write-Host "TinyUSB Test - Complete Deployment Scenario Testing" -ForegroundColor Yellow
Write-Host "Start Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Yellow

# 1-2. Idempotent: pico → pico (first set)
Deploy-Environment "pico" "Idempotent pico #1"
Deploy-Environment "pico" "Idempotent pico #2"

# 3. Transition: pico → pico_tinyUSB
Deploy-Environment "pico_tinyUSB" "Transition: pico → pico_tinyUSB #1"

# 4-5. Idempotent: pico_tinyUSB → pico_tinyUSB (first set)
Deploy-Environment "pico_tinyUSB" "Idempotent pico_tinyUSB #1"
Deploy-Environment "pico_tinyUSB" "Idempotent pico_tinyUSB #2"

# 6. Transition: pico_tinyUSB → pico
Deploy-Environment "pico" "Transition: pico_tinyUSB → pico"

# 7. Idempotent: pico → pico (second set)
Deploy-Environment "pico" "Idempotent pico #3"

# 8. Transition: pico → pico_tinyUSB (second)
Deploy-Environment "pico_tinyUSB" "Transition: pico → pico_tinyUSB #2"

# 9. Idempotent: pico_tinyUSB → pico_tinyUSB (second set)
Deploy-Environment "pico_tinyUSB" "Idempotent pico_tinyUSB #3"

# ============================================================================
# Final Summary
# ============================================================================

Write-Host ""
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Yellow
Write-Host "DEPLOYMENT TEST SUMMARY" -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Yellow
Write-Host "End Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-Host ""

$deployments | Format-Table -AutoSize Number, Environment, Description, Status, Duration

$totalDuration = ($deployments | Measure-Object -Property Duration -Sum).Sum
$successCount = ($deployments | Where-Object { $_.Status -eq "SUCCESS" }).Count
$failCount = ($deployments | Where-Object { $_.Status -ne "SUCCESS" }).Count

Write-Host "Total Deployments: $($deployments.Count)" -ForegroundColor Cyan
Write-Host "Successful: $successCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "Total Duration: $([math]::Round($totalDuration, 2)) seconds" -ForegroundColor Cyan

# Coverage Analysis
$picoCount = ($deployments | Where-Object { $_.Environment -eq "pico" }).Count
$tinyUSBCount = ($deployments | Where-Object { $_.Environment -eq "pico_tinyUSB" }).Count

Write-Host ""
Write-Host "Environment Coverage:" -ForegroundColor Cyan
Write-Host "  pico: $picoCount deployments" -ForegroundColor White
Write-Host "  pico_tinyUSB: $tinyUSBCount deployments" -ForegroundColor White

# Transition Analysis
$transitions = @()
for ($i = 1; $i -lt $deployments.Count; $i++) {
    $from = $deployments[$i-1].Environment
    $to = $deployments[$i].Environment
    if ($from -ne $to) {
        $transitions += "$from -> $to"
    }
}

Write-Host ""
Write-Host "Transitions Detected:" -ForegroundColor Cyan
$transitions | ForEach-Object { Write-Host "  $_" -ForegroundColor White }

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Yellow
if ($failCount -eq 0) {
    Write-Host "ALL TESTS PASSED" -ForegroundColor Green
} else {
    Write-Host "SOME TESTS FAILED" -ForegroundColor Red
}
Write-Host "============================================================================" -ForegroundColor Yellow

# Export results to JSON
$resultsFile = "test_results_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$deployments | ConvertTo-Json | Out-File $resultsFile
Write-Host ""
Write-Host "Results exported to: $resultsFile" -ForegroundColor Gray

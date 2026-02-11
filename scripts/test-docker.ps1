# Docker Image Testing Script
# Run this locally to validate your Docker image before deploying

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker Image Testing Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop and remove existing container
Write-Host "[Step 1/5] Cleaning up existing container..." -ForegroundColor Yellow
docker-compose down 2>$null

# Step 2: Build the image
Write-Host "[Step 2/5] Building Docker image..." -ForegroundColor Yellow
docker-compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker build failed!" -ForegroundColor Red
    Write-Host "  The build failed, which means dependencies are missing or there's a build error." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker build successful!" -ForegroundColor Green
Write-Host ""

# Step 3: Start the container
Write-Host "[Step 3/5] Starting container..." -ForegroundColor Yellow
docker-compose up -d
$containerId = docker ps --filter "name=amplifier-app-api" --format "{{.ID}}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to start container!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Container started (ID: $containerId)" -ForegroundColor Green
Write-Host ""

# Step 4: Wait for app to be ready
Write-Host "[Step 4/5] Waiting for app to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check container is still running
$running = docker ps --filter "id=$containerId" --format "{{.ID}}"
if (-not $running) {
    Write-Host "✗ Container crashed!" -ForegroundColor Red
    Write-Host "Container logs:" -ForegroundColor Red
    docker logs $containerId
    docker rm -f $containerId 2>$null
    exit 1
}
Write-Host "✓ Container is running" -ForegroundColor Green
Write-Host ""

# Step 5: Test HTTP endpoint
Write-Host "[Step 5/5] Testing HTTP endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8765" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ HTTP endpoint responding!" -ForegroundColor Green
    } else {
        Write-Host "✗ Unexpected status code: $($response.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ HTTP request failed: $_" -ForegroundColor Red
    Write-Host "Container logs:" -ForegroundColor Red
    docker logs $containerId
    docker rm -f $containerId
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Testing Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Container logs (last 20 lines):" -ForegroundColor Yellow
docker logs --tail 20 $containerId
Write-Host ""

# Cleanup
Write-Host "Cleaning up test container..." -ForegroundColor Yellow
docker-compose down | Out-Null
Write-Host "✓ Cleanup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "✓ All tests passed! Your image is ready to deploy." -ForegroundColor Green

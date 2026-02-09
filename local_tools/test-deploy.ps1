# Docker Image Testing Script
# Run this locally to validate your Docker image before deploying

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker Image Dev Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop existing Docker image
Write-Host "[Step 1/4] Stop existing Docker image..." -ForegroundColor Yellow
docker stop amplifier-app-api

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker failed to stop amplifier-app-api!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker stopped successfully!" -ForegroundColor Green
Write-Host ""

# Step 2: Build code and image
Write-Host "[Step 2/4] Building Docker image..." -ForegroundColor Yellow
docker-compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to build Docker image!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker image built successfully!" -ForegroundColor Green
Write-Host ""

# Step 3: Start the container
Write-Host "[Step 3/4] Starting container..." -ForegroundColor Yellow
docker-compose up -d --force-recreate

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to start container!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Container started!" -ForegroundColor Green
Write-Host ""

# Wait for app to be ready
Start-Sleep -Seconds 10

# Step 4: Test HTTP endpoint
Write-Host "[Step 4/4] Testing HTTP endpoint..." -ForegroundColor Yellow
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
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

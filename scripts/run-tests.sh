#!/bin/bash
# Run test suite with proper timeouts and reporting

set -e

echo "🧪 Running Amplifier App api Test Suite"
echo ""

cd /mnt/c/Users/malicata/source/amplifier-app-api

# Activate venv
source .venv/bin/activate 2>/dev/null || true

echo "📊 Test Suite Breakdown:"
echo ""

# 1. Database tests (fast, should all pass)
echo "1️⃣  Database Tests (17 tests)..."
timeout 30 .venv/bin/python -m pytest tests/test_database.py -v --tb=no -q | tail -3
echo ""

# 2. Model tests (fast, should all pass)
echo "2️⃣  Model Tests (24 tests)..."
timeout 30 .venv/bin/python -m pytest tests/test_models.py -v --tb=no -q | tail -3
echo ""

# 3. Smoke tests (fast, basic checks)
echo "3️⃣  Smoke Tests (13 tests)..."
timeout 30 .venv/bin/python -m pytest tests/test_smoke.py -v --tb=no -q | tail -3
echo ""

# 4. API tests (fast, basic endpoint validation)
echo "4️⃣  API Tests (10 tests)..."
timeout 30 .venv/bin/python -m pytest tests/test_api.py -v --tb=no -q | tail -3
echo ""

# Summary
echo "📈 Running Quick Summary..."
timeout 30 .venv/bin/python -m pytest \
  tests/test_database.py \
  tests/test_models.py \
  tests/test_smoke.py \
  tests/test_api.py \
  --tb=no -q 2>&1 | tail -5

echo ""
echo "✅ Fast test suite complete!"
echo ""
echo "Note: Comprehensive tests (sessions, config, bundles, tools, integration,"
echo "stress) require full amplifier-core setup and may take longer to run."
echo ""
echo "To run comprehensive tests:"
echo "  .venv/bin/python -m pytest tests/test_sessions_comprehensive.py -v"
echo "  .venv/bin/python -m pytest tests/test_config_comprehensive.py -v"
echo "  .venv/bin/python -m pytest tests/ -v  # All tests"

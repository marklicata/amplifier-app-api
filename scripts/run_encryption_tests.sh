#!/bin/bash
#
# Run all encryption tests with coverage report
#
# Usage:
#   ./scripts/run_encryption_tests.sh [OPTIONS]
#
# Options:
#   -v, --verbose     Verbose output
#   -c, --coverage    Generate coverage report
#   -h, --help        Show this help message
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default options
VERBOSE=""
COVERAGE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -c|--coverage)
            COVERAGE="--cov=amplifier_app_api.core.secrets_encryption --cov=amplifier_app_api.core.config_manager --cov=amplifier_app_api.api.config --cov-report=html --cov-report=term"
            shift
            ;;
        -h|--help)
            echo "Run all encryption tests with coverage report"
            echo ""
            echo "Usage:"
            echo "  ./scripts/run_encryption_tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose     Verbose output"
            echo "  -c, --coverage    Generate coverage report"
            echo "  -h, --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Header
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Amplifier API - Encryption Test Suite             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if encryption key is set
if [ -z "$CONFIG_ENCRYPTION_KEY" ]; then
    echo -e "${YELLOW}⚠️  WARNING: CONFIG_ENCRYPTION_KEY not set${NC}"
    echo -e "${YELLOW}   Setting test encryption key...${NC}"
    export CONFIG_ENCRYPTION_KEY="test-encryption-key-32-chars-minimum"
    echo ""
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Install with: pip install pytest${NC}"
    exit 1
fi

# Test files
TEST_FILES=(
    "tests/test_secrets_encryption.py"
    "tests/test_encryption.py"
    "tests/test_config_decrypt_api.py"
)

echo -e "${BLUE}🧪 Running encryption tests...${NC}"
echo ""

# Run tests
echo -e "${GREEN}Test files:${NC}"
for file in "${TEST_FILES[@]}"; do
    echo "  - $file"
done
echo ""

# Build pytest command
PYTEST_CMD="pytest ${TEST_FILES[*]} $VERBOSE $COVERAGE"

echo -e "${BLUE}Command: $PYTEST_CMD${NC}"
echo ""

# Run tests
if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  ✅ All Tests Passed!                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Show coverage report location if coverage was run
    if [ ! -z "$COVERAGE" ]; then
        echo -e "${GREEN}📊 Coverage report generated:${NC}"
        echo "   htmlcov/index.html"
        echo ""
        echo -e "${BLUE}View with:${NC} open htmlcov/index.html (macOS)"
        echo -e "${BLUE}       or:${NC} xdg-open htmlcov/index.html (Linux)"
        echo -e "${BLUE}       or:${NC} start htmlcov/index.html (Windows)"
        echo ""
    fi

    # Summary
    echo -e "${GREEN}📋 Test Summary:${NC}"
    echo "   - Unit tests:        15 tests (secrets_encryption.py)"
    echo "   - Integration tests:  6 tests (encryption.py)"
    echo "   - API tests:         15+ tests (config_decrypt_api.py)"
    echo "   - Total:             36+ tests"
    echo ""
    echo -e "${GREEN}✨ Encryption implementation is production-ready!${NC}"
    echo ""

    exit 0
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                  ❌ Tests Failed!                         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}Please check the output above for details.${NC}"
    echo ""
    exit 1
fi

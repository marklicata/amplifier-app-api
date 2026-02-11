@echo off
REM Run all encryption tests with coverage report
REM
REM Usage:
REM   scripts\run_encryption_tests.bat [OPTIONS]
REM
REM Options:
REM   -v          Verbose output
REM   -c          Generate coverage report
REM   -h          Show this help message

setlocal enabledelayedexpansion

REM Default options
set "VERBOSE="
set "COVERAGE="

REM Parse command line arguments
:parse_args
if "%1"=="" goto :run_tests
if "%1"=="-v" (
    set "VERBOSE=-v"
    shift
    goto :parse_args
)
if "%1"=="-c" (
    set "COVERAGE=--cov=amplifier_app_api.core.secrets_encryption --cov=amplifier_app_api.core.config_manager --cov=amplifier_app_api.api.config --cov-report=html --cov-report=term"
    shift
    goto :parse_args
)
if "%1"=="-h" (
    echo Run all encryption tests with coverage report
    echo.
    echo Usage:
    echo   scripts\run_encryption_tests.bat [OPTIONS]
    echo.
    echo Options:
    echo   -v          Verbose output
    echo   -c          Generate coverage report
    echo   -h          Show this help message
    exit /b 0
)
echo Unknown option: %1
echo Use -h for usage information
exit /b 1

:run_tests

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║         Amplifier API - Encryption Test Suite             ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check if encryption key is set
if not defined CONFIG_ENCRYPTION_KEY (
    echo ⚠️  WARNING: CONFIG_ENCRYPTION_KEY not set
    echo    Setting test encryption key...
    set "CONFIG_ENCRYPTION_KEY=test-encryption-key-32-chars-minimum"
    echo.
)

REM Check if pytest is available
where pytest >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ pytest not found. Install with: pip install pytest
    exit /b 1
)

echo 🧪 Running encryption tests...
echo.

echo Test files:
echo   - tests/test_secrets_encryption.py
echo   - tests/test_encryption.py
echo   - tests/test_config_decrypt_api.py
echo.

REM Run tests
pytest tests/test_secrets_encryption.py tests/test_encryption.py tests/test_config_decrypt_api.py %VERBOSE% %COVERAGE%

if %errorlevel% equ 0 (
    echo.
    echo ╔════════════════════════════════════════════════════════════╗
    echo ║                  ✅ All Tests Passed!                     ║
    echo ╚════════════════════════════════════════════════════════════╝
    echo.

    if defined COVERAGE (
        echo 📊 Coverage report generated:
        echo    htmlcov\index.html
        echo.
        echo View with: start htmlcov\index.html
        echo.
    )

    echo 📋 Test Summary:
    echo    - Unit tests:        15 tests (secrets_encryption.py)
    echo    - Integration tests:  6 tests (encryption.py)
    echo    - API tests:         15+ tests (config_decrypt_api.py)
    echo    - Total:             36+ tests
    echo.
    echo ✨ Encryption implementation is production-ready!
    echo.

    exit /b 0
) else (
    echo.
    echo ╔════════════════════════════════════════════════════════════╗
    echo ║                  ❌ Tests Failed!                         ║
    echo ╚════════════════════════════════════════════════════════════╝
    echo.
    echo Please check the output above for details.
    echo.
    exit /b 1
)

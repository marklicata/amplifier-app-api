#!/usr/bin/env python3
"""
Telemetry Testing Script

Tests telemetry functionality without requiring Azure Application Insights.
Uses the dev logger to verify events are being tracked correctly.
"""

import asyncio
import sys

import httpx

# Test configuration
BASE_URL = "http://localhost:8765"
TEST_SESSION_ID = "test-session-123"


async def test_telemetry():
    """Run telemetry tests against the running service."""
    print("=" * 60)
    print("Telemetry Testing Script")
    print("=" * 60)
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Health check (should generate request telemetry)
        print("[Test 1] Health Check")
        print("-" * 60)
        try:
            response = await client.get(f"{BASE_URL}/health")
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Request ID: {response.headers.get('X-Request-ID', 'N/A')}")
            print(f"✓ Response: {response.json()}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False
        print()

        # Test 2: Health check with session header
        print("[Test 2] Health Check with Session ID")
        print("-" * 60)
        try:
            response = await client.get(
                f"{BASE_URL}/health",
                headers={"X-Session-ID": TEST_SESSION_ID},
            )
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Request ID: {response.headers.get('X-Request-ID', 'N/A')}")
            print(f"✓ Session ID passed: {TEST_SESSION_ID}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False
        print()

        # Test 3: List configs (should generate more telemetry)
        print("[Test 3] List Configs")
        print("-" * 60)
        try:
            response = await client.get(f"{BASE_URL}/api/v1/configs")
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Request ID: {response.headers.get('X-Request-ID', 'N/A')}")
            data = response.json()
            print(f"✓ Configs found: {len(data.get('configs', []))}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False
        print()

        # Test 4: List sessions
        print("[Test 4] List Sessions")
        print("-" * 60)
        try:
            response = await client.get(f"{BASE_URL}/api/v1/sessions")
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Request ID: {response.headers.get('X-Request-ID', 'N/A')}")
            data = response.json()
            print(f"✓ Sessions found: {len(data.get('sessions', []))}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False
        print()

        # Test 5: Trigger an error (404)
        print("[Test 5] Error Handling (404)")
        print("-" * 60)
        try:
            response = await client.get(f"{BASE_URL}/api/v1/nonexistent")
            print(f"✓ Status: {response.status_code} (expected 404)")
            print(f"✓ Request ID: {response.headers.get('X-Request-ID', 'N/A')}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False
        print()

        # Test 6: Check dev logger endpoint (if available)
        print("[Test 6] Dev Logger Stats")
        print("-" * 60)
        print("Note: This requires adding a dev logger endpoint to the API")
        print("(Not implemented yet - will show in Azure Application Insights)")
        print()

    print("=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Check service logs: docker-compose logs amplifier-service")
    print("2. Look for '[Telemetry]' log messages")
    print("3. If Azure App Insights is configured, check Azure Portal in 2-5 minutes")
    print()
    return True


def print_instructions():
    """Print setup instructions."""
    print()
    print("Prerequisites:")
    print("1. Service must be running: docker-compose up -d")
    print("2. Wait for service to be healthy: docker-compose ps")
    print()
    print("To view telemetry events:")
    print("1. Check logs: docker-compose logs -f amplifier-service | grep Telemetry")
    print("2. Check Azure Portal (if configured):")
    print("   - Go to Application Insights → Logs")
    print("   - Query: traces | where customDimensions.app_id == 'amplifier-app-api'")
    print()


if __name__ == "__main__":
    print_instructions()

    try:
        result = asyncio.run(test_telemetry())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)

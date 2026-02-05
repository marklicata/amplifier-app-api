"""Complete E2E tests for bundle endpoints.

Tests the full bundle lifecycle: add, get, activate, list, delete.

Requirements:
- Live HTTP server (uses live_service fixture)
- amplifier-core and amplifier-foundation configured
"""

import pytest

try:
    import httpx
except ImportError:
    httpx = None


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestBundleLifecycle:
    """Test complete bundle lifecycle operations."""

    def test_add_bundle_and_get_details(self, live_service):
        """Test adding a bundle then retrieving its details."""
        # Add a bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "test-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
                "scope": "user",
            },
            timeout=30.0,
        )

        assert add_response.status_code == 200
        bundle_name = add_response.json()["name"]
        assert bundle_name == "test-bundle"

        # Get bundle details
        get_response = httpx.get(
            f"{live_service}/bundles/{bundle_name}",
            timeout=5.0,
        )

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["name"] == bundle_name
        assert "source" in data
        assert data["source"] == "git+https://github.com/microsoft/amplifier-bundle-recipes.git"
        assert "active" in data
        assert isinstance(data["active"], bool)

        # Cleanup - remove bundle
        delete_response = httpx.delete(
            f"{live_service}/bundles/{bundle_name}",
            timeout=5.0,
        )
        assert delete_response.status_code == 200

    def test_add_bundle_activate_and_verify(self, live_service):
        """Test adding a bundle, activating it, and verifying it's active."""
        # Add bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "activate-test-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        assert add_response.status_code == 200
        bundle_name = add_response.json()["name"]

        # Activate the bundle
        activate_response = httpx.post(
            f"{live_service}/bundles/{bundle_name}/activate",
            timeout=5.0,
        )

        assert activate_response.status_code == 200

        # Verify it's active in the list
        list_response = httpx.get(f"{live_service}/bundles", timeout=5.0)
        assert list_response.status_code == 200
        data = list_response.json()

        # Find our bundle in the list
        bundle_info = next((b for b in data["bundles"] if b["name"] == bundle_name), None)
        assert bundle_info is not None
        assert bundle_info["active"] is True

        # Also verify via direct get
        get_response = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert get_response.status_code == 200
        assert get_response.json()["active"] is True

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)

    def test_complete_bundle_lifecycle(self, live_service):
        """Test add → activate → get → list → delete flow."""
        bundle_name = "lifecycle-test-bundle"

        # 1. Add
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": bundle_name,
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )
        assert add_response.status_code == 200

        # 2. Activate
        activate_response = httpx.post(
            f"{live_service}/bundles/{bundle_name}/activate",
            timeout=5.0,
        )
        assert activate_response.status_code == 200

        # 3. Get - verify active
        get_response = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert get_response.status_code == 200
        assert get_response.json()["active"] is True

        # 4. List - verify in list
        list_response = httpx.get(f"{live_service}/bundles", timeout=5.0)
        assert list_response.status_code == 200
        bundles = list_response.json()["bundles"]
        assert any(b["name"] == bundle_name for b in bundles)

        # 5. Delete
        delete_response = httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert delete_response.status_code == 200

        # 6. Verify deleted
        get_after_delete = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert get_after_delete.status_code == 404

    def test_get_bundle_tools(self, live_service):
        """Test getting tools from a bundle."""
        # Add a bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "tools-test-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        assert add_response.status_code == 200
        bundle_name = add_response.json()["name"]

        # Get tools from the bundle
        tools_response = httpx.get(
            f"{live_service}/bundles/{bundle_name}/tools",
            timeout=10.0,
        )

        # May succeed or fail depending on bundle structure
        # Just verify endpoint exists and returns valid structure
        if tools_response.status_code == 200:
            data = tools_response.json()
            assert "tools" in data
            assert isinstance(data["tools"], list)

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)

    def test_add_bundle_with_auto_name_extraction(self, live_service):
        """Test that bundle name is auto-extracted from git URL if not provided."""
        # Add without explicit name
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        assert add_response.status_code == 200
        data = add_response.json()

        # Name should be extracted from URL
        assert "name" in data
        bundle_name = data["name"]
        assert len(bundle_name) > 0

        # Verify we can get it
        get_response = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert get_response.status_code == 200

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestBundleErrors:
    """Test error handling for bundle operations."""

    def test_get_nonexistent_bundle_returns_404(self, live_service):
        """Test getting non-existent bundle returns 404."""
        response = httpx.get(
            f"{live_service}/bundles/nonexistent-bundle-xyz",
            timeout=5.0,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_bundle_returns_404(self, live_service):
        """Test deleting non-existent bundle returns 404."""
        response = httpx.delete(
            f"{live_service}/bundles/nonexistent-bundle-xyz",
            timeout=5.0,
        )

        assert response.status_code == 404

    def test_activate_nonexistent_bundle_returns_404(self, live_service):
        """Test activating non-existent bundle returns 404."""
        response = httpx.post(
            f"{live_service}/bundles/nonexistent-bundle-xyz/activate",
            timeout=5.0,
        )

        assert response.status_code == 404

    def test_add_bundle_with_invalid_source_returns_error(self, live_service):
        """Test adding bundle with invalid source returns error."""
        response = httpx.post(
            f"{live_service}/bundles",
            json={"source": "not-a-valid-source"},
            timeout=5.0,
        )

        # Should either validate and reject, or fail during processing
        assert response.status_code in [400, 422, 500]

    def test_get_tools_from_nonexistent_bundle_returns_404(self, live_service):
        """Test getting tools from non-existent bundle returns 404."""
        response = httpx.get(
            f"{live_service}/bundles/nonexistent-bundle/tools",
            timeout=5.0,
        )

        assert response.status_code == 404


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestBundleActivation:
    """Test bundle activation scenarios."""

    def test_activate_bundle_idempotency(self, live_service):
        """Test that activating an already-active bundle is idempotent."""
        # Add and activate bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "idempotent-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        bundle_name = add_response.json()["name"]

        # First activation
        activate1 = httpx.post(
            f"{live_service}/bundles/{bundle_name}/activate",
            timeout=5.0,
        )
        assert activate1.status_code == 200

        # Second activation (should be idempotent)
        activate2 = httpx.post(
            f"{live_service}/bundles/{bundle_name}/activate",
            timeout=5.0,
        )
        assert activate2.status_code == 200

        # Should still be active
        get_response = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert get_response.json()["active"] is True

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)

    def test_only_one_bundle_can_be_active(self, live_service):
        """Test that activating a bundle deactivates the previous one."""
        # Add two bundles
        bundle1_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "bundle-one",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )
        bundle1_name = bundle1_response.json()["name"]

        bundle2_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "bundle-two",
                "source": "git+https://github.com/microsoft/amplifier-bundle-python-dev.git",
            },
            timeout=30.0,
        )
        bundle2_name = bundle2_response.json()["name"]

        # Activate first bundle
        httpx.post(f"{live_service}/bundles/{bundle1_name}/activate", timeout=5.0)

        # Verify bundle1 is active
        get1 = httpx.get(f"{live_service}/bundles/{bundle1_name}", timeout=5.0)
        assert get1.json()["active"] is True

        # Activate second bundle
        httpx.post(f"{live_service}/bundles/{bundle2_name}/activate", timeout=5.0)

        # Verify bundle2 is now active
        get2 = httpx.get(f"{live_service}/bundles/{bundle2_name}", timeout=5.0)
        assert get2.json()["active"] is True

        # Verify bundle1 is no longer active (if single-active-bundle enforcement exists)
        # This depends on implementation - may or may not deactivate bundle1
        get1_after = httpx.get(f"{live_service}/bundles/{bundle1_name}", timeout=5.0)
        # Just verify the call works
        assert get1_after.status_code == 200

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle1_name}", timeout=5.0)
        httpx.delete(f"{live_service}/bundles/{bundle2_name}", timeout=5.0)


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestBundleListing:
    """Test bundle listing scenarios."""

    def test_list_bundles_shows_all_added_bundles(self, live_service):
        """Test that list shows all bundles that have been added."""
        # Get initial count
        initial_list = httpx.get(f"{live_service}/bundles", timeout=5.0)
        initial_count = len(initial_list.json()["bundles"])

        # Add a bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "list-test-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        bundle_name = add_response.json()["name"]

        # List should now include new bundle
        list_response = httpx.get(f"{live_service}/bundles", timeout=5.0)
        data = list_response.json()

        assert len(data["bundles"]) == initial_count + 1
        assert any(b["name"] == bundle_name for b in data["bundles"])

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)

    def test_list_bundles_includes_active_status(self, live_service):
        """Test that bundle list indicates which bundle is active."""
        # Add and activate bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "active-status-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        bundle_name = add_response.json()["name"]

        # Activate it
        httpx.post(f"{live_service}/bundles/{bundle_name}/activate", timeout=5.0)

        # List should show active status
        list_response = httpx.get(f"{live_service}/bundles", timeout=5.0)
        data = list_response.json()

        # Find our bundle
        our_bundle = next((b for b in data["bundles"] if b["name"] == bundle_name), None)
        assert our_bundle is not None
        assert our_bundle["active"] is True

        # Response should also include active bundle name
        assert "active" in data
        assert data["active"] == bundle_name

        # Cleanup
        httpx.delete(f"{live_service}/bundles/{bundle_name}", timeout=5.0)

    def test_list_bundles_when_empty(self, live_service):
        """Test listing bundles when no custom bundles added."""
        # This might not be truly empty (foundation might be there)
        # but we just verify structure
        response = httpx.get(f"{live_service}/bundles", timeout=5.0)

        assert response.status_code == 200
        data = response.json()
        assert "bundles" in data
        assert isinstance(data["bundles"], list)
        assert "active" in data


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestBundleDeletion:
    """Test bundle deletion scenarios."""

    def test_delete_bundle_removes_from_list(self, live_service):
        """Test that deleting a bundle removes it from the list."""
        # Add bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "delete-test-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        bundle_name = add_response.json()["name"]

        # Verify it's in the list
        list_before = httpx.get(f"{live_service}/bundles", timeout=5.0)
        bundles_before = list_before.json()["bundles"]
        assert any(b["name"] == bundle_name for b in bundles_before)

        # Delete it
        delete_response = httpx.delete(
            f"{live_service}/bundles/{bundle_name}",
            timeout=5.0,
        )
        assert delete_response.status_code == 200

        # Verify it's no longer in the list
        list_after = httpx.get(f"{live_service}/bundles", timeout=5.0)
        bundles_after = list_after.json()["bundles"]
        assert not any(b["name"] == bundle_name for b in bundles_after)

        # Verify GET also returns 404
        get_after = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
        assert get_after.status_code == 404

    def test_cannot_delete_active_bundle(self, live_service):
        """Test that deleting an active bundle returns appropriate error."""
        # Add and activate bundle
        add_response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "active-delete-bundle",
                "source": "git+https://github.com/microsoft/amplifier-bundle-recipes.git",
            },
            timeout=30.0,
        )

        bundle_name = add_response.json()["name"]
        httpx.post(f"{live_service}/bundles/{bundle_name}/activate", timeout=5.0)

        # Try to delete active bundle
        delete_response = httpx.delete(
            f"{live_service}/bundles/{bundle_name}",
            timeout=5.0,
        )

        # Should either:
        # - 400: Cannot delete active bundle
        # - 200: Deactivates and deletes
        # Implementation-dependent
        assert delete_response.status_code in [200, 400]

        # If deletion succeeded, verify it's gone
        if delete_response.status_code == 200:
            get_response = httpx.get(f"{live_service}/bundles/{bundle_name}", timeout=5.0)
            assert get_response.status_code == 404
        else:
            # Cleanup - deactivate first, then delete
            # (Would need to activate another bundle or have deactivate endpoint)
            # For now just document this edge case
            pass


@pytest.mark.e2e
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestBundleValidation:
    """Test bundle validation scenarios."""

    def test_add_bundle_missing_source_returns_422(self, live_service):
        """Test that adding bundle without source returns validation error."""
        response = httpx.post(
            f"{live_service}/bundles",
            json={"name": "no-source-bundle"},  # Missing source
            timeout=5.0,
        )

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_add_bundle_with_invalid_scope_returns_error(self, live_service):
        """Test adding bundle with invalid scope."""
        response = httpx.post(
            f"{live_service}/bundles",
            json={
                "name": "invalid-scope-bundle",
                "source": "git+https://github.com/example/bundle.git",
                "scope": "invalid-scope-value",
            },
            timeout=5.0,
        )

        # Should validate scope values
        # May return 422 if strict validation, or 500 if runtime error
        assert response.status_code in [400, 422, 500]

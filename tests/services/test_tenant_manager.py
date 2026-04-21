"""Tests for the tenant management system."""

import tempfile

import pytest

from src.services.tenant_manager import Tenant, TenantManager


class TestTenant:
    """Tests for the Tenant dataclass."""

    def test_tenant_creation(self):
        """Test basic tenant creation."""
        tenant = Tenant(id="tenant-1", name="Test Tenant")
        assert tenant.id == "tenant-1"
        assert tenant.name == "Test Tenant"
        assert tenant.config == {}

    def test_tenant_with_config(self):
        """Test tenant creation with config."""
        config = {"max_tasks": 100, "priority": "high"}
        tenant = Tenant(id="tenant-2", name="Config Tenant", config=config)
        assert tenant.config == config

    def test_empty_tenant_id_raises(self):
        """Test that empty tenant ID raises ValueError."""
        with pytest.raises(ValueError, match="Tenant ID cannot be empty"):
            Tenant(id="", name="Empty")

    def test_tenant_id_with_slash_raises(self):
        """Test that tenant ID with slash raises ValueError."""
        with pytest.raises(ValueError, match="Tenant ID cannot contain path separators"):
            Tenant(id="tenant/path", name="Bad Path")

    def test_tenant_id_with_backslash_raises(self):
        """Test that tenant ID with backslash raises ValueError."""
        with pytest.raises(ValueError, match="Tenant ID cannot contain path separators"):
            Tenant(id="tenant\\path", name="Bad Path")


class TestTenantManager:
    """Tests for the TenantManager class."""

    def setup_method(self):
        """Set up a fresh TenantManager for each test."""
        self.manager = TenantManager()

    def test_default_tenant_exists(self):
        """Test that default tenant is created automatically."""
        default = self.manager.get_tenant("default")
        assert default is not None
        assert default.name == "Default Tenant"

    def test_create_tenant(self):
        """Test creating a new tenant."""
        tenant = self.manager.create_tenant("acme-corp", "Acme Corporation")
        assert tenant.id == "acme-corp"
        assert tenant.name == "Acme Corporation"

        # Verify it can be retrieved
        retrieved = self.manager.get_tenant("acme-corp")
        assert retrieved == tenant

    def test_create_duplicate_tenant_raises(self):
        """Test that creating duplicate tenant raises ValueError."""
        self.manager.create_tenant("unique-id", "Unique")
        with pytest.raises(ValueError, match="Tenant 'unique-id' already exists"):
            self.manager.create_tenant("unique-id", "Duplicate")

    def test_get_nonexistent_tenant(self):
        """Test that getting non-existent tenant returns None."""
        assert self.manager.get_tenant("does-not-exist") is None

    def test_get_or_create_tenant(self):
        """Test get_or_create_tenant creates new tenant."""
        # Create new tenant
        tenant = self.manager.get_or_create_tenant("new-tenant", "New Tenant")
        assert tenant.id == "new-tenant"
        assert tenant.name == "New Tenant"

        # Subsequent calls should return same tenant
        same_tenant = self.manager.get_or_create_tenant("new-tenant")
        assert same_tenant == tenant

    def test_get_or_create_tenant_generates_name(self):
        """Test get_or_create_tenant generates name if not provided."""
        tenant = self.manager.get_or_create_tenant("generated-name")
        assert "generated-name" in tenant.name

    def test_update_tenant(self):
        """Test updating tenant name and config."""
        self.manager.create_tenant("update-me", "Original Name", {"key": "value"})

        updated = self.manager.update_tenant(
            "update-me", name="New Name", config={"new_key": "new_value"}
        )

        assert updated.name == "New Name"
        assert updated.config == {"key": "value", "new_key": "new_value"}

    def test_update_nonexistent_tenant_raises(self):
        """Test updating non-existent tenant raises ValueError."""
        with pytest.raises(ValueError, match="Tenant 'nonexistent' not found"):
            self.manager.update_tenant("nonexistent", name="New Name")

    def test_delete_tenant(self):
        """Test deleting a tenant."""
        self.manager.create_tenant("delete-me", "To Delete")
        self.manager.delete_tenant("delete-me")
        assert self.manager.get_tenant("delete-me") is None

    def test_delete_default_tenant_raises(self):
        """Test that deleting default tenant raises ValueError."""
        with pytest.raises(ValueError, match="Cannot delete the default tenant"):
            self.manager.delete_tenant("default")

    def test_delete_nonexistent_tenant_raises(self):
        """Test that deleting non-existent tenant raises ValueError."""
        with pytest.raises(ValueError, match="Tenant 'missing' not found"):
            self.manager.delete_tenant("missing")

    def test_list_tenants(self):
        """Test listing all tenants."""
        self.manager.create_tenant("t1", "Tenant 1")
        self.manager.create_tenant("t2", "Tenant 2")

        tenants = self.manager.list_tenants()
        assert len(tenants) == 3  # default + 2 new
        ids = {t.id for t in tenants}
        assert ids == {"default", "t1", "t2"}


class TestTenantFilePaths:
    """Tests for tenant-specific file path generation."""

    def setup_method(self):
        """Set up a fresh TenantManager for each test."""
        self.manager = TenantManager()
        self.manager.create_tenant("acme-corp", "Acme Corp")

    def test_default_tenant_state_filename(self):
        """Test default tenant uses base filename for state."""
        filename = self.manager.get_state_filename("default", "state.json")
        assert filename == "state.json"

    def test_default_tenant_events_filename(self):
        """Test default tenant uses base filename for events."""
        filename = self.manager.get_event_filename("default", "events.jsonl")
        assert filename == "events.jsonl"

    def test_custom_tenant_state_filename(self):
        """Test custom tenant gets namespaced state filename."""
        filename = self.manager.get_state_filename("acme-corp", "state.json")
        assert filename == "state.acme-corp.json"

    def test_custom_tenant_events_filename(self):
        """Test custom tenant gets namespaced events filename."""
        filename = self.manager.get_event_filename("acme-corp", "events.jsonl")
        assert filename == "events.acme-corp.jsonl"

    def test_base_path_integration(self):
        """Test file paths with custom base path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TenantManager(base_path=tmpdir)
            manager.create_tenant("custom", "Custom")

            state_file = manager.get_state_filename("custom")
            assert tmpdir in state_file
            assert "state.custom.json" in state_file

    def test_get_tenant_files(self):
        """Test getting all file paths for a tenant."""
        files = self.manager.get_tenant_files("acme-corp")
        assert files["state"] == "state.acme-corp.json"
        assert files["events"] == "events.acme-corp.jsonl"


class TestTenantManagerIntegration:
    """Integration tests combining multiple operations."""

    def test_tenant_lifecycle(self):
        """Test full tenant lifecycle: create, update, use, delete."""
        manager = TenantManager()

        # Create tenant
        tenant = manager.create_tenant("lifecycle-test", "Lifecycle Test")
        assert tenant.id == "lifecycle-test"

        # Update tenant
        manager.update_tenant("lifecycle-test", config={"setting": "value"})
        updated = manager.get_tenant("lifecycle-test")
        assert updated.config["setting"] == "value"

        # Get files
        files = manager.get_tenant_files("lifecycle-test")
        assert "lifecycle-test" in files["state"]

        # Delete tenant
        manager.delete_tenant("lifecycle-test")
        assert manager.get_tenant("lifecycle-test") is None

    def test_multiple_tenants_isolation(self):
        """Test that multiple tenants have isolated file paths."""
        manager = TenantManager()

        manager.create_tenant("tenant-a", "Tenant A")
        manager.create_tenant("tenant-b", "Tenant B")

        files_a = manager.get_tenant_files("tenant-a")
        files_b = manager.get_tenant_files("tenant-b")

        assert files_a["state"] != files_b["state"]
        assert files_a["events"] != files_b["events"]
        assert "tenant-a" in files_a["state"]
        assert "tenant-b" in files_b["state"]

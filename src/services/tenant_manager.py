"""Multi-tenant support for state management.

Provides tenant isolation through namespace-specific file paths
and tenant-aware state management.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Tenant:
    """Represents a tenant with isolated state storage.

    Attributes:
        id: Unique tenant identifier (used in file paths)
        name: Human-readable tenant name
        config: Optional tenant-specific configuration
    """

    id: str
    name: str
    config: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate tenant ID format."""
        if not self.id:
            raise ValueError("Tenant ID cannot be empty")
        if "/" in self.id or "\\" in self.id:
            raise ValueError("Tenant ID cannot contain path separators")


class TenantManager:
    """Manages tenant lifecycle and tenant-specific file paths.

    Provides CRUD operations for tenants and generates isolated
    file paths for state and event storage per tenant.
    """

    DEFAULT_TENANT_ID = "default"

    def __init__(self, base_path: str = "."):
        """Initialize the tenant manager.

        Args:
            base_path: Base directory for tenant state files
        """
        self._base_path = Path(base_path)
        self._tenants: dict[str, Tenant] = {}
        self._ensure_default_tenant()

    def _ensure_default_tenant(self) -> None:
        """Create the default tenant if it doesn't exist."""
        if self.DEFAULT_TENANT_ID not in self._tenants:
            self._tenants[self.DEFAULT_TENANT_ID] = Tenant(
                id=self.DEFAULT_TENANT_ID,
                name="Default Tenant",
                config={},
            )

    def create_tenant(self, tenant_id: str, name: str, config: Optional[dict] = None) -> Tenant:
        """Create a new tenant.

        Args:
            tenant_id: Unique identifier for the tenant
            name: Human-readable tenant name
            config: Optional tenant-specific configuration

        Returns:
            The created Tenant instance

        Raises:
            ValueError: If tenant_id already exists or is invalid
        """
        if tenant_id in self._tenants:
            raise ValueError(f"Tenant '{tenant_id}' already exists")

        tenant = Tenant(id=tenant_id, name=name, config=config or {})
        self._tenants[tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID.

        Args:
            tenant_id: The tenant identifier

        Returns:
            The Tenant instance or None if not found
        """
        return self._tenants.get(tenant_id)

    def get_or_create_tenant(self, tenant_id: str, name: str = "", config: Optional[dict] = None) -> Tenant:
        """Get an existing tenant or create a new one.

        Args:
            tenant_id: The tenant identifier
            name: Human-readable name (used if creating new)
            config: Optional configuration (used if creating new)

        Returns:
            Existing or newly created Tenant instance
        """
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            tenant_name = name or f"Tenant {tenant_id}"
            tenant = self.create_tenant(tenant_id, tenant_name, config)
        return tenant

    def update_tenant(self, tenant_id: str, name: Optional[str] = None, config: Optional[dict] = None) -> Tenant:
        """Update an existing tenant.

        Args:
            tenant_id: The tenant identifier
            name: New name (optional)
            config: New config (optional, merges with existing)

        Returns:
            Updated Tenant instance

        Raises:
            ValueError: If tenant doesn't exist
        """
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        if name is not None:
            tenant.name = name
        if config is not None:
            tenant.config.update(config)

        return tenant

    def delete_tenant(self, tenant_id: str) -> None:
        """Delete a tenant.

        Args:
            tenant_id: The tenant identifier

        Raises:
            ValueError: If trying to delete the default tenant or if tenant doesn't exist
        """
        if tenant_id == self.DEFAULT_TENANT_ID:
            raise ValueError("Cannot delete the default tenant")
        if tenant_id not in self._tenants:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        del self._tenants[tenant_id]

    def list_tenants(self) -> list[Tenant]:
        """List all registered tenants.

        Returns:
            List of Tenant instances
        """
        return list(self._tenants.values())

    def get_state_filename(self, tenant_id: str, base_filename: str = "state.json") -> str:
        """Generate tenant-specific state filename.

        Args:
            tenant_id: The tenant identifier
            base_filename: Base filename pattern

        Returns:
            Tenant-specific file path
        """
        if tenant_id == self.DEFAULT_TENANT_ID:
            return str(self._base_path / base_filename)

        # Insert tenant_id before the extension
        path = Path(base_filename)
        tenant_filename = f"{path.stem}.{tenant_id}{path.suffix}"
        return str(self._base_path / tenant_filename)

    def get_event_filename(self, tenant_id: str, base_filename: str = "events.jsonl") -> str:
        """Generate tenant-specific events filename.

        Args:
            tenant_id: The tenant identifier
            base_filename: Base filename pattern

        Returns:
            Tenant-specific file path
        """
        if tenant_id == self.DEFAULT_TENANT_ID:
            return str(self._base_path / base_filename)

        # Insert tenant_id before the extension
        path = Path(base_filename)
        tenant_filename = f"{path.stem}.{tenant_id}{path.suffix}"
        return str(self._base_path / tenant_filename)

    def get_tenant_files(self, tenant_id: str) -> dict[str, str]:
        """Get all file paths for a tenant.

        Args:
            tenant_id: The tenant identifier

        Returns:
            Dictionary with 'state' and 'events' file paths
        """
        return {
            "state": self.get_state_filename(tenant_id),
            "events": self.get_event_filename(tenant_id),
        }


def get_default_tenant_manager() -> TenantManager:
    """Get or create the default tenant manager singleton."""
    return TenantManager()

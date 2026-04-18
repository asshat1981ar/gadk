from dataclasses import dataclass

from src.capabilities.contracts import CapabilityHandler


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    description: str
    backend: str
    handler: CapabilityHandler


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        backend: str,
        handler: CapabilityHandler,
    ) -> None:
        if name in self._capabilities:
            msg = f"Capability '{name}' is already registered"
            raise ValueError(msg)

        self._capabilities[name] = CapabilityDefinition(
            name=name,
            description=description,
            backend=backend,
            handler=handler,
        )

    def get(self, name: str) -> CapabilityDefinition:
        return self._capabilities[name]

"""Layer 0 capability descriptions shared by TRACE32 backends."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BackendCapabilities:
    """Runtime capability snapshot for one connected backend."""

    backend: str
    services: dict[str, bool] = field(default_factory=dict)
    features: dict[str, bool] = field(default_factory=dict)
    breakpoint: dict[str, list[str]] = field(default_factory=dict)

    def supports(self, capability: str) -> bool:
        """Return whether a dotted service/feature name is advertised."""

        if capability in self.features:
            return bool(self.features[capability])
        if capability.startswith("service."):
            return bool(self.services.get(capability.removeprefix("service."), False))
        return False

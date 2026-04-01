from __future__ import annotations

from net_maestro.core.models.component_config import ComponentConfig


class SwitchConfig(ComponentConfig):
    def __str__(self) -> str:
        return f"SwitchConfig - {self.model}"

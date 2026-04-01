from __future__ import annotations

from net_maestro.core.models.component_config import ComponentConfig


class RouterConfig(ComponentConfig):
    def __str__(self) -> str:
        return f"RouterConfig - {self.model}"

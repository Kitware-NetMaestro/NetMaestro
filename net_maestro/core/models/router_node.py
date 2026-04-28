from __future__ import annotations

from net_maestro.core.models.node import Node


class RouterNode(Node):
    def __str__(self) -> str:
        return f"Router Node - {self.name}"

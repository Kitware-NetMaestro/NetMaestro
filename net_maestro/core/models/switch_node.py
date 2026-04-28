from __future__ import annotations

from net_maestro.core.models.node import Node


class SwitchNode(Node):
    def __str__(self) -> str:
        return f"Switch Node - {self.name}"

from __future__ import annotations

from django.db import models
from django.db.models import Max


class Topology(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Topology {self.id}: {self.name}"

    def next_order_index(self) -> int:
        """Use the next unused order_index for a node in this topology.

        Deleting a node in the middle leaves its index unused rather than renumbering, because
        renumbering would move every terminal after it and invalidate any trace produced against
        the old indices.
        """
        highest = self.nodes.aggregate(highest=Max("order_index"))["highest"]
        return 0 if highest is None else highest + 1

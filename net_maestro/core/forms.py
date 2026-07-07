"""Django forms for NetMaestro."""

from __future__ import annotations

from typing import Any

from django import forms

from .models import PHOLDSimulationConfig


class PHOLDSimulationForm(forms.ModelForm):
    """Form for PHOLD simulation parameters.

    A ModelForm bound to PHOLDSimulationConfig so field validators are not duplicated
    between the model and a plain Form.
    """

    # run_identifier maps to Run.name, not a PHOLDSimulationConfig field,
    # so it must be declared explicitly.
    run_identifier = forms.CharField(
        label="Run Identifier",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    )

    # Rendered as a Select (Yes/No) rather than the default checkbox widget.
    stagger = forms.TypedChoiceField(
        label="Stagger Events",
        choices=[(0, "No"), (1, "Yes")],
        coerce=lambda value: str(value) == "1",
        initial=0,
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    class Meta:
        model = PHOLDSimulationConfig
        fields = [
            "synch",
            "avl_size",
            "nlp",
            "remote",
            "mean",
            "mult",
            "lookahead",
            "start_events",
            "memory",
            "stagger",
        ]
        labels = {
            "synch": "Synchronization Protocol",
            "avl_size": "AVL Tree Size",
            "nlp": "LPs per Processor",
            "remote": "Remote Event Rate",
            "mean": "Mean Timestamp",
            "mult": "Memory Multiplier",
            "start_events": "Start Events per LP",
            "memory": "Additional Memory Buffers",
        }
        widgets = {
            "synch": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "avl_size": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "nlp": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "remote": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "step": "0.01"}
            ),
            "mean": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "step": "0.1"}
            ),
            "mult": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "step": "0.1"}
            ),
            "lookahead": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "step": "0.1"}
            ),
            "start_events": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "memory": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # model_to_dict() surfaces the model's boolean value for stagger,
        # but the widget's choices are keyed by 0/1.
        if "stagger" in self.initial:
            self.initial["stagger"] = int(bool(self.initial["stagger"]))

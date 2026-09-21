"""Django forms for NetMaestro."""

from __future__ import annotations

import json
from typing import Any

from django import forms

from .base_models import BASE_MODEL_BY_NAME, BASE_MODEL_REGISTRY
from .models import ComponentModel, PHOLDSimulationConfig


class ComponentModelForm(forms.ModelForm):
    base_model = forms.ChoiceField(
        choices=[("", "Select a base model")]
        + [(m["name"], m["name"]) for m in BASE_MODEL_REGISTRY],
        widget=forms.Select(
            attrs={"class": "select select-bordered w-full"},
        ),
    )

    class Meta:
        model = ComponentModel
        fields = ["name", "base_model", "component_type", "engine", "description", "parameters"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "component_type": forms.HiddenInput(),
            "engine": forms.HiddenInput(),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
            "parameters": forms.HiddenInput(),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["component_type"].required = False
        self.fields["engine"].required = False
        self.fields["description"].required = False
        if self.initial.get("parameters") is None:
            self.initial["parameters"] = {}
        if self.instance and self.instance.parameters is None:
            self.initial.setdefault("parameters", {})

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        if cleaned is None:
            return {}
        base_name = cleaned.get("base_model", "")
        meta = BASE_MODEL_BY_NAME.get(base_name)
        if not meta:
            self.add_error("base_model", "Select a valid base model.")
            return cleaned
        cleaned["component_type"] = meta["component_type"]
        cleaned["engine"] = meta["engine"]
        params_json = self.data.get("parameters", "")
        if params_json:
            try:
                parsed = json.loads(params_json)
            except (json.JSONDecodeError, TypeError):
                self.add_error("parameters", "Invalid JSON in parameters.")
                return cleaned
            if not isinstance(parsed, dict):
                self.add_error("parameters", "Parameters must be a JSON object.")
                return cleaned
            allowed = {
                (p["name"] if isinstance(p, dict) else p) for p in meta.get("parameters", [])
            }
            unknown = set(parsed.keys()) - allowed
            if unknown:
                self.add_error(
                    "parameters",
                    f"Unknown parameter(s): {', '.join(sorted(unknown))}",
                )
                return cleaned
            cleaned["parameters"] = parsed
        return cleaned


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

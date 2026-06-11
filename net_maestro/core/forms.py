"""Django forms for NetMaestro."""

from __future__ import annotations

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator


class PHOLDSimulationForm(forms.Form):
    """Form for PHOLD simulation parameters."""

    # Simulation Model section
    run_identifier = forms.CharField(
        label="Run Identifier",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    )

    # Engine Parameters
    synch = forms.ChoiceField(
        label="Synchronization Protocol",
        choices=[
            (1, "Sequential"),
            (2, "Conservative"),
            (3, "Optimistic"),
            (4, "Optimistic Debug"),
            (5, "Optimistic Realtime"),
            (6, "Reverse Handler Check"),
        ],
        initial=3,
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    avl_size = forms.IntegerField(
        label="AVL Tree Size",
        initial=18,
        validators=[MinValueValidator(10), MaxValueValidator(24)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
    )

    # Model Parameters
    nlp = forms.IntegerField(
        label="LPs per Processor",
        initial=8,
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
    )

    remote = forms.FloatField(
        label="Remote Event Rate",
        initial=0.25,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "0.01"}),
    )

    mean = forms.FloatField(
        label="Mean Timestamp",
        initial=1.0,
        validators=[MinValueValidator(0.1)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "0.1"}),
    )

    mult = forms.FloatField(
        label="Memory Multiplier",
        initial=1.4,
        validators=[MinValueValidator(1.0)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "0.1"}),
    )

    lookahead = forms.FloatField(
        label="Lookahead",
        initial=1.0,
        validators=[MinValueValidator(0.1)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "0.1"}),
    )

    start_events = forms.IntegerField(
        label="Start Events per LP",
        initial=1,
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
    )

    memory = forms.IntegerField(
        label="Additional Memory Buffers",
        initial=100,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
    )

    stagger = forms.ChoiceField(
        label="Stagger Events",
        choices=[(0, "No"), (1, "Yes")],
        initial=0,
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

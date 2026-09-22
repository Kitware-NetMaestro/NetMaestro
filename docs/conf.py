"""Sphinx configuration for NetMaestro documentation."""

from __future__ import annotations

project = "NetMaestro"
copyright = "2026, Kitware"  # noqa: A001
author = "Kitware"

extensions = [
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

myst_heading_anchors = 3

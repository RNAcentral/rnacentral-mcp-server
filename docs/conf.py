"""Sphinx configuration for the RNAcentral MCP Server documentation."""

project = "RNAcentral MCP Server"
author = "RNAcentral"
copyright = "2026, RNAcentral"
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
master_doc = "index"

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
    "substitution",
]

html_theme = "sphinx_rtd_theme"
html_title = "RNAcentral MCP Server"
html_static_path = ["_static"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

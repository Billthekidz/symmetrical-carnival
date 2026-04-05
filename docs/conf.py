# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
project = "Polymarket Watcher"
copyright = "2024, Billthekidz"
author = "Billthekidz"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML output options -----------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "navigation_depth": 4,
    "titles_only": False,
}

# -- MyST parser options -----------------------------------------------------
myst_enable_extensions = ["colon_fence"]
# Treat ```mermaid code fences as the {mermaid} directive so
# sphinxcontrib-mermaid renders them.
myst_fence_as_directive = ["mermaid"]

# -- Autodoc options ---------------------------------------------------------
# Mock third-party packages so autodoc can import modules without needing
# the runtime dependencies to be installed in the docs build environment.
autodoc_mock_imports = ["websockets", "requests", "yaml"]
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"

# -- Mermaid options ---------------------------------------------------------
# Use the CDN-based JavaScript renderer (no server-side binary required).
# This works out of the box on GitHub Pages.
mermaid_version = "11"

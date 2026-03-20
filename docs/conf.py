"""Sphinx configuration for QVideo."""

import os
import sys
from pathlib import Path

# Use Qt's offscreen platform so pyqtgraph can be imported by autodoc
# without a display (required on ReadTheDocs and other headless build hosts).
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# The repo root is one level up from docs/.  Adding it to sys.path lets
# autodoc import QVideo without requiring an editable install.
sys.path.insert(0, str(Path(__file__).parent.parent))

# -- Project information -----------------------------------------------------

project = 'QVideo'
author = 'David G. Grier'
copyright = '2026, David G. Grier'
from importlib.metadata import version as _get_version
release = _get_version('QVideo')

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
]

# Napoleon settings for NumPy-style docstrings
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_param = False
napoleon_use_rtype = False

# autodoc settings
autodoc_member_order = 'bysource'
autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'show-inheritance': True,
}

# Optional hardware dependencies that cannot be imported on a doc-build host
autodoc_mock_imports = [
    'harvesters',
    'genicam',
    'PySpin',
    'picamera2',
]

# intersphinx: link to external package docs
intersphinx_mapping = {
    'python':    ('https://docs.python.org/3', None),
    'numpy':     ('https://numpy.org/doc/stable', None),
    'pyqtgraph': ('https://pyqtgraph.readthedocs.io/en/latest', None),
}

templates_path = ['_templates']
exclude_patterns = ['_build']

# -- HTML output -------------------------------------------------------------

html_theme = 'pydata_sphinx_theme'
html_title = 'QVideo'
html_static_path = ['_static']
html_css_files = ['nyu.css']

html_theme_options = {
    'github_url': 'https://github.com/davidgrier/QVideo',
    'show_toc_level': 2,
    'navigation_with_keys': True,
    'show_nav_level': 2,
    'navbar_end': ['navbar-icon-links', 'theme-switcher'],
    'footer_start': ['copyright'],
    'footer_end': ['sphinx-version'],
}

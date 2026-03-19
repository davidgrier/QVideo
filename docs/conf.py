"""Sphinx configuration for QVideo."""

import sys
from pathlib import Path

# The repo root is one level up from docs/.  Adding it to sys.path lets
# autodoc import QVideo without requiring an editable install.
sys.path.insert(0, str(Path(__file__).parent.parent))

# -- Project information -----------------------------------------------------

project = 'QVideo'
author = 'David Grier'
release = '3.0.0'

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
    'numba',
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

html_theme = 'furo'
html_title = 'QVideo'

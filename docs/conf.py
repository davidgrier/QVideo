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

exclude_patterns = ['_build']


def setup(app):
    '''Suppress spurious duplicate-object warnings from Sphinx 8.x.

    Sphinx 8.x's ObjectDescription generates class member directives both
    inside the class body (via parse_content_to_nodes) and as a separate
    top-level list.  This causes every method/attribute to be registered
    twice, triggering "duplicate object description" warnings.  The fix
    marks the second registration as an alias so it silently defers to the
    first without emitting a warning.
    '''
    from sphinx.domains.python import PythonDomain
    _orig = PythonDomain.note_object
    _seen = {}

    def _dedup(self, name, objtype, node_id, aliased=False, location=None):
        if not aliased and name in _seen:
            # Second occurrence: register as alias to suppress duplicate warning
            return _orig(self, name, objtype, node_id, aliased=True,
                         location=location)
        if not aliased:
            _seen[name] = self.env.docname
        return _orig(self, name, objtype, node_id, aliased, location)

    PythonDomain.note_object = _dedup

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

# The site is small enough that the top navbar covers all navigation.
# Suppress the primary (left) sidebar so it doesn't appear empty on
# leaf pages that have no toctree children.
html_sidebars = {'**': []}

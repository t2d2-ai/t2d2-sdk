# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
sys.path.insert(0, os.path.abspath('../../src'))

project = 'T2D2 SDK'
copyright = '2024, Badri Hiriyur'
author = 'Badri Hiriyur'
release = 'v1.5'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.coverage', 'sphinx.ext.napoleon', 'myst_parser', 'sphinx.ext.githubpages']

templates_path = ['_templates']
exclude_patterns = []

myst_heading_anchors = 3

# -- Options for autodoc -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': False,
    'exclude-members': '__weakref__'
}
# Mock imports that cause permission issues or aren't needed for documentation
autodoc_mock_imports = [
    'boto3',
    'botocore',
    'sentry_sdk',
    'docx',
    'PIL',
    'matplotlib',
    'numpy',
    'condition_report_service'
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = 'nature'
html_theme_options = {
    # Nature theme doesn't have many custom options
}
html_static_path = ['_static']
html_show_sourcelink = False  # Hide "View page source" links
suppress_warnings = ["myst.header"]  # This will suppress the header level warnings

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
#  Mistral documentation build configuration file
#
# Refer to the Sphinx documentation for advice on configuring this file:
#
#   http://www.sphinx-doc.org/en/stable/config.html

import os
import sys

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

sys.path.insert(0, os.path.abspath('../../'))
sys.path.insert(0, os.path.abspath('../'))
sys.path.insert(0, os.path.abspath('./'))

# -- General configuration ----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.

extensions = [
    'sphinx.ext.autodoc',
    'sphinxcontrib.pecanwsme.rest',
    'sphinxcontrib.httpdomain',
    'wsmeext.sphinxext',
    'openstackdocstheme',
    'oslo_policy.sphinxext',
    'oslo_policy.sphinxpolicygen',
]

wsme_protocols = ['restjson']

suppress_warnings = ['app.add_directive']

# The suffix of source file names.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'Mistral'
copyright = '2023, Mistral Contributors'

policy_generator_config_file = \
    '../../tools/config/policy-generator.mistral.conf'
sample_policy_basename = '_static/mistral'

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
show_authors = False

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'native'

# -- Options for HTML output --------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
# html_static_path = ['_static']

html_theme = 'openstackdocs'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ['mistral.']

# The name for this set of Sphinx documents. If None, it defaults to
# "<project> v<release> documentation".
html_title = 'Mistral'

# -- Options for manual page output -------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'mistral', 'Mistral',
     ['OpenStack Foundation'], 1)
]

# If true, show URL addresses after external links.
man_show_urls = True

# -- Options for openstackdocstheme -------------------------------------------

openstackdocs_repo_name = 'openstack/mistral'
openstackdocs_pdf_link = True
openstackdocs_auto_name = False
openstackdocs_bug_project = 'mistral'
openstackdocs_bug_tag = 'doc'

latex_use_xindy = False

html_theme_options = {
    "display_global_toc_section": True,
    "sidebar_mode": "toctree",
}

# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    'makeindex': '',
    'printindex': '',
    'preamble': r'\setcounter{tocdepth}{3}',
}

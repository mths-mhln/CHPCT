Installation
============

Dependencies
------------

- Python 3.13 or newer.
- CoolProp, matplotlib, numpy, rich and scipy. The versions are listed in ``pyproject.toml``, the exact versions that were used in ``uv.lock``.
- NIST REFPROP. All fluid properties are evaluated with REFPROP through CoolProp, hence a licensed REFPROP installation is required. The tool does not fall back on the CoolProp equations of state.
- A LaTeX installation, since the text in the diagrams is rendered with LaTeX.

Installing the tool
-------------------

The tool is installed in editable mode in a virtual environment, which was made with `uv <https://docs.astral.sh/uv/>`_. This makes both the ``CHPC`` package and the local copy of thermoplot in ``src/thermoplot`` importable.

.. code-block:: bash

   git clone https://github.com/mths-mhln/CHPCT.git
   cd CHPCT
   uv venv
   .venv\Scripts\activate
   uv pip install -e .

On Linux or macOS the environment is activated with ``source .venv/bin/activate`` instead. A regular ``python -m venv .venv`` followed by ``pip install -e .`` should work as well.

Building this documentation
---------------------------

Sphinx is not part of the dependencies of the tool, so it has to be installed separately with ``pip install sphinx``. The html pages are then built with

.. code-block:: bash

   cd docs
   make html

and can be found in ``docs/build/html``.

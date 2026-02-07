"""Linguistics layer: surface form generation per language.

Each language module (en.py, pl.py, ...) provides a surface_form() function.
They are registered with the dispatch module on import.
"""

from littera.linguistics import dispatch, en, pl

dispatch.register("en", en.surface_form)
dispatch.register("pl", pl.surface_form)

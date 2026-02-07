"""Language dispatch for surface form generation.

Each language module registers its surface_form function here.
Callers use dispatch.surface_form(language, ...) without knowing
which module handles which language.
"""

from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, Callable] = {}


def register(language: str, func: Callable) -> None:
    """Register a surface_form function for a language code."""
    _REGISTRY[language] = func


def surface_form(
    language: str,
    base_form: str,
    features: dict | None = None,
    properties: dict | None = None,
) -> str:
    """Dispatch to the appropriate language module's surface_form."""
    func = _REGISTRY.get(language)
    if func is None:
        return base_form
    return func(base_form, features, properties)

"""Domain rules shared by every interface (CLI, TUI, desktop server).

Rules that decide what may be written to the database live here, not in a
single interface.  Three interfaces now write to the same database; a guard
that lives in only one of them is a guard that can be walked around.
"""

from littera.domain.guards import (
    GuardViolation,
    ensure_alignment_languages_differ,
    ensure_entity_exists,
    find_entity,
)

__all__ = [
    "GuardViolation",
    "ensure_alignment_languages_differ",
    "ensure_entity_exists",
    "find_entity",
]

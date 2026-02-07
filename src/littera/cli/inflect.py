"""Preview command: littera inflect <base_form> [--plural] [--possessive] [--article a|the]

Generates an English surface form without touching the database.
"""

from __future__ import annotations

from typing import Optional

import typer

from littera.linguistics.en import surface_form


def register(app: typer.Typer) -> None:
    @app.command()
    def inflect(
        base_form: str = typer.Argument(help="Base form of the word"),
        plural: bool = typer.Option(False, "--plural", help="Pluralize"),
        possessive: bool = typer.Option(False, "--possessive", help="Add possessive"),
        article: Optional[str] = typer.Option(
            None, "--article", help="Article: 'a' or 'the'"
        ),
    ) -> None:
        """Preview English surface form generation."""
        features: dict = {}
        if plural:
            features["number"] = "pl"
        if possessive:
            features["case"] = "poss"
        if article:
            if article not in ("a", "the"):
                print(f"Invalid article: {article} (must be 'a' or 'the')")
                raise typer.Exit(1)
            features["article"] = article

        result = surface_form(base_form, features or None)
        print(result)

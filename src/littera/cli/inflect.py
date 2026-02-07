"""Preview command: littera inflect <base_form> [--lang en|pl] [options]

Generates a surface form without touching the database.
Dispatches to the appropriate language module.
"""

from __future__ import annotations

from typing import Optional

import typer

from littera.linguistics.dispatch import surface_form


def register(app: typer.Typer) -> None:
    @app.command()
    def inflect(
        base_form: str = typer.Argument(help="Base form of the word"),
        lang: str = typer.Option("en", "--lang", help="Language code: 'en' or 'pl'"),
        plural: bool = typer.Option(False, "--plural", help="Pluralize"),
        possessive: bool = typer.Option(False, "--possessive", help="Add possessive (English only)"),
        article: Optional[str] = typer.Option(
            None, "--article", help="Article: 'a' or 'the' (English only)"
        ),
        case: Optional[str] = typer.Option(
            None, "--case", help="Case: 'plain'|'poss' (en) or 'nom'|'gen'|'dat'|'acc'|'inst'|'loc'|'voc' (pl)"
        ),
        gender: Optional[str] = typer.Option(
            None, "--gender", help="Gender: 'm1'|'m2'|'m3'|'f'|'n' (Polish only)"
        ),
        countable: Optional[str] = typer.Option(
            None, "--countable", help="Countability: 'yes' or 'no' (English only)"
        ),
    ) -> None:
        """Preview surface form generation for any supported language."""
        # Validate language-specific flag conflicts
        if lang == "pl":
            if possessive:
                print("Error: --possessive is English only. Use --case=gen for Polish genitive.")
                raise typer.Exit(1)
            if article:
                print("Error: --article is English only. Polish has no articles.")
                raise typer.Exit(1)

        features: dict = {}
        if plural:
            features["number"] = "pl"

        # --possessive is sugar for --case=poss (English)
        if possessive and case:
            print("Error: --possessive and --case are mutually exclusive.")
            raise typer.Exit(1)

        if possessive:
            features["case"] = "poss"
        elif case:
            features["case"] = case

        if article:
            if article not in ("a", "the"):
                print(f"Invalid article: {article} (must be 'a' or 'the')")
                raise typer.Exit(1)
            features["article"] = article

        properties: dict | None = None
        if countable is not None:
            if countable not in ("yes", "no"):
                print(f"Invalid countable value: {countable} (must be 'yes' or 'no')")
                raise typer.Exit(1)
            properties = {"countable": countable}

        if gender is not None:
            properties = properties or {}
            properties["gender"] = gender

        result = surface_form(lang, base_form, features or None, properties)
        print(result)

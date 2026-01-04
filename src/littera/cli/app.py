"""Main CLI application wiring for Littera.

This module:
- defines the root Typer app
- registers subcommands
- contains no business logic
"""

import typer

from littera.cli import init as init_cmd
from littera.cli import status as status_cmd
from littera.cli import doc as doc_cmd
from littera.cli import section as section_cmd
from littera.cli import block as block_cmd
from littera.cli import block_edit as block_edit_cmd
from littera.cli import block_manage as block_manage_cmd

app = typer.Typer(add_completion=False, help="Littera — literature meets refactoring")


@app.callback()
def main():
    """Littera CLI."""
    pass


# Register commands
init_cmd.register(app)
status_cmd.register(app)
doc_cmd.register(app)
section_cmd.register(app)
block_cmd.register(app)
block_edit_cmd.register(app)
block_manage_cmd.register(app)

from littera.cli import entity as entity_cmd
from littera.cli import mention as mention_cmd
from littera.cli import entity_note as entity_note_cmd
from littera.cli import mntn_db as mntn_db_cmd

entity_cmd.register(app)
mention_cmd.register(app)
entity_note_cmd.register(app)
mntn_db_cmd.register(app)


@app.command()
def tui():
    """Launch the Littera TUI."""
    from littera.tui.app import LitteraApp

    LitteraApp().run()

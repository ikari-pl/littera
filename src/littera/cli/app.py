"""Main CLI application wiring for Littera.

kubectl-style subcommands:
  littera doc add "Title"
  littera docs list
  littera block delete 1

Both singular and plural forms work identically.
"""

import typer

app = typer.Typer(add_completion=False, help="Littera — structure meets writing")


@app.callback()
def main():
    """Littera CLI."""
    pass


# =============================================================================
# Subcommand groups
# =============================================================================

# Documents
doc_app = typer.Typer(help="Manage documents")
app.add_typer(doc_app, name="doc")
app.add_typer(doc_app, name="docs")

# Sections
section_app = typer.Typer(help="Manage sections")
app.add_typer(section_app, name="section")
app.add_typer(section_app, name="sections")

# Blocks
block_app = typer.Typer(help="Manage blocks")
app.add_typer(block_app, name="block")
app.add_typer(block_app, name="blocks")

# Entities
entity_app = typer.Typer(help="Manage entities")
app.add_typer(entity_app, name="entity")
app.add_typer(entity_app, name="entities")

# Mentions
mention_app = typer.Typer(help="Manage mentions")
app.add_typer(mention_app, name="mention")
app.add_typer(mention_app, name="mentions")


# =============================================================================
# Register commands to subgroups
# =============================================================================

from littera.cli import doc as doc_cmd
from littera.cli import section as section_cmd
from littera.cli import block as block_cmd
from littera.cli import entity as entity_cmd
from littera.cli import entity_note as entity_note_cmd
from littera.cli import entity_label as entity_label_cmd
from littera.cli import mention as mention_cmd

doc_cmd.register(doc_app)
section_cmd.register(section_app)
block_cmd.register(block_app)
entity_cmd.register(entity_app)
entity_note_cmd.register(entity_app)  # adds note-set and note-show to entity subgroup
entity_label_cmd.register(entity_app)  # adds label-add, label-list, label-delete
mention_cmd.register(mention_app)


# =============================================================================
# Top-level commands
# =============================================================================

from littera.cli import init as init_cmd
from littera.cli import status as status_cmd
from littera.cli import mntn_db as mntn_db_cmd
from littera.cli import inflect as inflect_cmd

init_cmd.register(app)
status_cmd.register(app)
mntn_db_cmd.register(app)
inflect_cmd.register(app)


@app.command()
def tui():
    """Launch the Littera TUI."""
    from littera.tui.app import LitteraApp

    LitteraApp().run()

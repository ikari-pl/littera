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

# Alignments
alignment_app = typer.Typer(help="Manage block alignments")
app.add_typer(alignment_app, name="alignment")
app.add_typer(alignment_app, name="alignments")

# Reviews
review_app = typer.Typer(help="Manage reviews")
app.add_typer(review_app, name="review")
app.add_typer(review_app, name="reviews")

# Export / Import
export_app = typer.Typer(help="Export work data")
app.add_typer(export_app, name="export")

import_app = typer.Typer(help="Import work data")
app.add_typer(import_app, name="import")


# =============================================================================
# Register commands to subgroups
# =============================================================================

from littera.cli import doc as doc_cmd
from littera.cli import section as section_cmd
from littera.cli import block as block_cmd
from littera.cli import entity as entity_cmd
from littera.cli import entity_note as entity_note_cmd
from littera.cli import entity_label as entity_label_cmd
from littera.cli import entity_property as entity_property_cmd
from littera.cli import mention as mention_cmd
from littera.cli import alignment as alignment_cmd
from littera.cli import review as review_cmd
from littera.cli import entity_suggest as entity_suggest_cmd

doc_cmd.register(doc_app)
section_cmd.register(section_app)
block_cmd.register(block_app)
entity_cmd.register(entity_app)
entity_note_cmd.register(entity_app)  # adds note-set and note-show to entity subgroup
entity_label_cmd.register(entity_app)  # adds label-add, label-list, label-delete
entity_property_cmd.register(entity_app)  # adds property-set, property-list, property-delete
entity_suggest_cmd.register(entity_app)  # adds suggest-label
mention_cmd.register(mention_app)
alignment_cmd.register(alignment_app)
review_cmd.register(review_app)

from littera.cli import io as io_cmd

io_cmd.register_export(export_app)
io_cmd.register_import(import_app)


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

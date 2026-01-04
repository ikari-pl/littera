from textual.widgets import ListView, ListItem, Static
from littera.tui.views.base import View
from littera.tui.state import AppState


class DocumentsView(View):
    name = "documents"

    def render(self, state: AppState):
        items = []
        cur = state.db.cursor()
        cur.execute("SELECT id, title FROM documents ORDER BY created_at")
        for doc_id, title in cur.fetchall():
            items.append(ListItem(Static(f"📄 {title}"), id=str(doc_id)))
        return [ListView(*items, id="documents")]

    def handle_key(self, key: str, state: AppState) -> bool:
        return False

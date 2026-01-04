# Littera CLI

The CLI is the primary interface and the product contract.
If it works in the CLI, it will work everywhere.

---

## Command Structure

```
littera <noun> <verb> [options]
```

Core nouns:
- work
- doc
- section
- block
- entity
- align
- review
- edit

---

## Examples

Initialize a work:
```
littera init my-work
```

Edit in full-screen TUI:
```
littera edit
```

List entities:
```
littera entity list
```

Change entity gender (preview required):
```
littera entity set anna --gender masc
```

---

## Output Modes

- Human-readable by default
- `--json` for scripting and automation

JSON is **never** used for prose storage.

---

## Safety Features

- `--dry-run`
- Explicit confirmations
- Explainable diffs

The CLI never performs destructive actions implicitly.

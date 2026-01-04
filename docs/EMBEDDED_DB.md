# Embedded Database Strategy

> **Literature meets refactoring — without asking the user to install a database.**

This document defines how Littera handles persistent storage in a way that is:
- zero‑maintenance for end users
- offline‑first
- deterministic and reproducible
- aligned with long‑term feature goals

This is a *product decision*, not merely an implementation detail.

---

## Decision Summary (Locked)

- ✅ Littera ships with **bundled Postgres server binaries**
- ✅ No external database installation is required
- ✅ SQLite is **not** supported as a backend
- ✅ Docker is **not** used for end users

Postgres is embedded because it is the *semantic backbone* Littera requires.

---

## Why Not SQLite

SQLite was explicitly considered and rejected.

While SQLite is excellent for many applications, for Littera it would:
- remove JSONB semantics
- limit future graph‑like queries
- complicate alignment and consistency checks
- create a hard migration cliff later

Choosing SQLite would *reduce* functionality while *increasing* complexity.

Littera prefers:
> **one powerful engine used everywhere**

---

## Why Not Docker

Docker is inappropriate for Littera’s target users.

Reasons:
- requires system‑level setup
- requires a background daemon
- breaks offline simplicity
- complicates desktop distribution

Docker may be used for **development or CI**, but never as a runtime dependency.

---

## What “Embedded Postgres” Means

In Littera, *embedded Postgres* means:

- Postgres server binaries are **downloaded and managed by Littera**
- Each work has its **own isolated Postgres cluster**
- The database lives inside the work directory:

```
.my-work/
└─ .littera/
   ├─ pg/
   │  ├─ bin/
   │  ├─ lib/
   │  └─ share/
   ├─ pgdata/
   └─ config.yml
```

No global state is modified.
No system services are registered.

---

## Port Strategy

Littera must coexist safely with any system‑installed Postgres.

### Rules

- Littera **never** uses the default Postgres port (5432)
- Each work uses a port chosen from a **high, uncommon range**
- Port choice is deterministic but configurable

### Default Strategy

- Base range: `55432–55999`
- On `littera init`:
  - scan for a free port in this range
  - record it in `.littera/config.yml`

This avoids:
- collisions with system databases
- surprises for advanced users

---

## Versioning Strategy

- Littera pins a **specific Postgres major version** per release
- All users of a given Littera version run the same Postgres version
- Upgrades are handled explicitly by Littera

This guarantees:
- reproducibility
- consistent behavior
- predictable migrations

---

## Offline Guarantees

- Embedded Postgres works fully offline
- All binaries are local after first download
- No network access is required for normal operation

Network is used only for:
- initial binary download
- optional LLM features

---

## Security Model

- Database listens only on `localhost`
- Uses a Unix socket where possible
- Authentication is local and automatic
- No external access unless explicitly configured

Littera never exposes a database to the network by default.

---

## Responsibilities Split

### CLI / Application Layer

- chooses Postgres version
- downloads binaries if missing
- selects port
- manages lifecycle (start/stop)

### Database Layer

- initializes cluster
- runs server
- applies schema

### Domain Layer

- remains unaware of how Postgres is provided

This separation preserves architectural clarity.

---

## Non‑Goals

The embedded database system does NOT:
- support remote connections by default
- attempt multi‑user access
- auto‑upgrade across major versions silently

These may be added later, explicitly.

---

## Final Note

Bundling Postgres is a deliberate choice.

It trades:
- a larger binary size

for:
- correctness
- power
- trust
- zero maintenance

For Littera, this trade is worth it.

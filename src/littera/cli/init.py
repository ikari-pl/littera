"""
`littera init` command.

Policy layer:
- chooses defaults
- writes config
- orchestrates bootstrap
"""

from pathlib import Path
import yaml

from littera.db.bootstrap import PostgresConfig, bootstrap


def register(app):
    import typer

    @app.command()
    def init(
        path: Path = typer.Argument(Path.cwd(), help="Directory for the new work"),
        db_port: int = typer.Option(0, help="Postgres port (0 = auto)"),
    ):
        try:
            import psycopg
        except ImportError as e:
            raise RuntimeError("psycopg is required to initialize a work") from e

        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)

        littera_dir = path / ".littera"
        littera_dir.mkdir(exist_ok=True)

        # Policy: choose a free port if none provided
        if db_port:
            port = db_port
        else:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                port = s.getsockname()[1]

        # Create a single Work for this repository
        import uuid

        work_id = str(uuid.uuid4())

        cfg = {
            "work": {
                "id": work_id,
            },
            "postgres": {
                "data_dir": str(littera_dir / "pgdata"),
                "port": port,
                "db_name": "littera",
            },
        }

        config_path = littera_dir / "config.yml"
        with config_path.open("w") as f:
            yaml.safe_dump(cfg, f)

        # Ensure embedded Postgres binaries
        from littera.db.embedded_pg import EmbeddedPostgresManager

        manager = EmbeddedPostgresManager(littera_dir)
        manager.ensure()

        pg_cfg = PostgresConfig(
            data_dir=Path(cfg["postgres"]["data_dir"]),
            port=cfg["postgres"]["port"],
            db_name=cfg["postgres"]["db_name"],
            initdb_path=str(manager.initdb_path()),
            pg_ctl_path=str(manager.pg_ctl_path()),
        )

        bootstrap(pg_cfg)

        # Ensure application database exists
        admin_conn = psycopg.connect(
            dbname=pg_cfg.admin_db,  # usually 'postgres'
            port=pg_cfg.port,
        )
        admin_conn.autocommit = True
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (pg_cfg.db_name,),
            )
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{pg_cfg.db_name}"')
        admin_conn.close()

        # Apply schema
        conn = psycopg.connect(
            dbname=pg_cfg.db_name,
            port=pg_cfg.port,
        )
        schema_path = Path(__file__).parents[3] / "db" / "schema.sql"
        with schema_path.open() as f:
            conn.execute(f.read())
        conn.commit()

        # Ensure Work row exists
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM works WHERE id = %s",
                (cfg["work"]["id"],),
            )
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO works (id, title) VALUES (%s, %s)",
                    (cfg["work"]["id"], path.name),
                )
        conn.commit()
        conn.close()

        # Treat embedded Postgres like an implementation detail.
        from littera.db.bootstrap import stop_postgres

        stop_postgres(pg_cfg)

        print(f"Initialized Littera work at {path}")

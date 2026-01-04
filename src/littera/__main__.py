"""
Littera CLI entrypoint.

Executed via:
  python -m littera

Assumes dependencies are installed in an isolated environment.
"""

from littera.cli.app import app

if __name__ == "__main__":
    app()

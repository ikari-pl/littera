"""Embedded Postgres manager (macOS, initial implementation).

This module is responsible for acquiring and managing a bundled Postgres
distribution for Littera.

For developer experience and test performance, Postgres binaries are cached
globally under the user home directory and symlinked into each work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import platform
import shutil
import tarfile
import urllib.request
import zipfile


POSTGRES_VERSION = "18.1.0"

# Redistributable embedded Postgres binaries via Maven Central (Zonky)
# Artifacts are JARs containing native Postgres distributions
# GroupId: io.zonky.test.postgres
MACOS_BINARIES = {
    # Apple Silicon
    "arm64": {
        "url": "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-darwin-arm64v8/18.1.0/embedded-postgres-binaries-darwin-arm64v8-18.1.0.jar",
        "sha1": "5941b043f17fe3deca920763efd2fc38ed2f0efa",
    },
    # Intel
    "x86_64": {
        "url": "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-darwin-amd64/18.1.0/embedded-postgres-binaries-darwin-amd64-18.1.0.jar",
        "sha1": "ade1f82936188b591844e9bc5bcfc22443b0d71f",
    },
}


class EmbeddedPostgresError(RuntimeError):
    pass


@dataclass
class EmbeddedPostgresManager:
    base_dir: Path  # .littera directory

    @property
    def pg_dir(self) -> Path:
        return self.base_dir / "pg"

    @property
    def bin_dir(self) -> Path:
        # Zonky artifacts end up with binaries under pg/bin
        return self.pg_dir / "bin"

    def ensure(self) -> None:
        """Ensure Postgres binaries exist in the work.

        Binaries are cached globally and symlinked into the work directory.
        """
        if self.bin_dir.exists():
            return

        cached_pg_dir = self._ensure_cached_binaries()
        self._populate_work_pg_dir(cached_pg_dir)

    def initdb_path(self) -> Path:
        return self.bin_dir / "initdb"

    def postgres_path(self) -> Path:
        return self.bin_dir / "postgres"

    def pg_ctl_path(self) -> Path:
        return self.bin_dir / "pg_ctl"

    # ---------------- internal ----------------

    def _cache_root(self) -> Path:
        system = platform.system().lower()
        arch = platform.machine()
        return (
            Path.home()
            / ".cache"
            / "littera"
            / "embedded-postgres"
            / POSTGRES_VERSION
            / f"{system}-{arch}"
        )

    def _ensure_cached_binaries(self) -> Path:
        cache_root = self._cache_root()
        cached_pg_dir = cache_root / "pg"
        cached_bin_dir = cached_pg_dir / "bin"

        if cached_bin_dir.exists():
            return cached_pg_dir

        cached_pg_dir.mkdir(parents=True, exist_ok=True)
        self._download_and_unpack(cached_pg_dir)
        if not cached_bin_dir.exists():
            raise EmbeddedPostgresError("Cached Postgres binaries are incomplete")

        return cached_pg_dir

    def _populate_work_pg_dir(self, cached_pg_dir: Path) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

        if self.pg_dir.exists() or self.pg_dir.is_symlink():
            if self.pg_dir.is_symlink() or self.pg_dir.is_file():
                self.pg_dir.unlink()
            else:
                shutil.rmtree(self.pg_dir)

        try:
            self.pg_dir.symlink_to(cached_pg_dir, target_is_directory=True)
        except OSError:
            shutil.copytree(cached_pg_dir, self.pg_dir)

    def _download_and_unpack(self, pg_dir: Path) -> None:
        system = platform.system()
        if system != "Darwin":
            raise EmbeddedPostgresError(f"Unsupported platform: {system}")

        arch = platform.machine()
        if arch not in MACOS_BINARIES:
            raise EmbeddedPostgresError(f"Unsupported architecture: {arch}")

        binary_info = MACOS_BINARIES[arch]
        url = binary_info["url"]
        expected_sha1 = binary_info["sha1"]

        archive_path = pg_dir / "postgres.jar"

        with urllib.request.urlopen(url) as resp, archive_path.open("wb") as out:
            shutil.copyfileobj(resp, out)

        # Verify download integrity
        actual_sha1 = hashlib.sha1(archive_path.read_bytes()).hexdigest()
        if actual_sha1 != expected_sha1:
            archive_path.unlink()
            raise EmbeddedPostgresError(
                f"Checksum mismatch for {url}: "
                f"expected {expected_sha1}, got {actual_sha1}"
            )

        # 1. Extract JAR (ZIP)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(pg_dir)

        archive_path.unlink()

        # 2. Extract embedded .txz (native Postgres)
        txz_files = list(pg_dir.glob("postgres-*.txz"))
        if not txz_files:
            raise EmbeddedPostgresError(
                "No embedded Postgres .txz found in Zonky artifact"
            )

        txz_path = txz_files[0]
        with tarfile.open(txz_path, mode="r:xz") as tf:
            tf.extractall(pg_dir)

        txz_path.unlink()

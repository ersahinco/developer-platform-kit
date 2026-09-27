"""Build the native permission integration and load it into the local Kind cluster."""

import hashlib
from pathlib import Path
import subprocess

SOURCE = Path(__file__).resolve().parent / "backstage"
IMAGE = (
    "developer-platform-backstage:"
    + hashlib.sha256(
        b"".join(
            path.name.encode() + path.read_bytes()
            for path in sorted(SOURCE.iterdir())
            if path.is_file()
        )
    ).hexdigest()[:20]
)

if __name__ == "__main__":
    present = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    if present.returncode:
        subprocess.run(
            [
                "docker",
                "build",
                # The pinned CNOE image runs through Docker emulation on ARM.
                # Keep a single manifest, matching upstream, for Kind imports.
                "--provenance=false",
                "--platform",
                "linux/amd64",
                "-t",
                IMAGE,
                str(SOURCE),
            ],
            check=True,
        )
    subprocess.run(["kind", "load", "docker-image", "--name", "toolkit", IMAGE], check=True)

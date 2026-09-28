"""Validate the rendered infra root against this checkout, without cloud access."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from scaffold.new_repo import example_values, load_template, render, resolve_values


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    template = load_template("infra")
    with tempfile.TemporaryDirectory(prefix="toolkit-infra-") as directory:
        root = Path(directory)
        render(template, root, resolve_values(template, example_values(template)))
        for path in root.glob("*.tf"):
            path.write_text(
                re.sub(
                    r'git::https://github.com/[^" ]+//modules/aws/([a-z0-9-]+)\?ref=[^" ]+',
                    lambda match: str(repository / "modules/aws" / match[1]),
                    path.read_text(),
                )
            )
        (root / "tests").mkdir()
        shutil.copyfile(repository / "tests/infra.tftest.hcl", root / "tests/infra.tftest.hcl")
        for command in [
            ("init", "-backend=false", "-input=false"),
            ("validate",),
            ("test", "-no-color", "-var-file=stack.tfvars"),
        ]:
            subprocess.run(["terraform", f"-chdir={root}", *command], check=True)


if __name__ == "__main__":
    main()

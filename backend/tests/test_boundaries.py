import os
import subprocess
import sys
from pathlib import Path


def test_core_boundary_check_rejects_framework_and_adapter_imports(
    tmp_path: Path,
) -> None:
    package = tmp_path / "lumiere"
    package.mkdir()
    for module in ("", "domain", "application", "adapters"):
        directory = package / module
        directory.mkdir(exist_ok=True)
        (directory / "__init__.py").write_text("")
    for module in ("bootstrap", "config"):
        (package / f"{module}.py").write_text("")
    (package / "domain/__init__.py").write_text(
        "import pydantic\nimport lumiere.adapters\n"
    )
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("lint-imports")),
            "--no-cache",
            "--config",
            str(Path(__file__).parents[1] / "pyproject.toml"),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "BROKEN" in result.stdout
    assert "lumiere.domain -> pydantic" in result.stdout
    assert "lumiere.domain -> lumiere.adapters" in result.stdout

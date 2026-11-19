import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(("layer", "statement"), [("domain", "import fastapi"), ("application", "import lumiere.adapters.outbound.persistence.models")])
def test_real_import_linter_rejects_forbidden_edges(layer: str, statement: str) -> None:
    probe = ROOT / "src/lumiere" / layer / "_architecture_probe.py"
    probe.write_text(statement + "\n")
    try:
        result = subprocess.run([str(Path(sys.executable).with_name("lint-imports")), "--no-cache"], cwd=ROOT, capture_output=True, text=True, check=False)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "BROKEN" in result.stdout
    finally:
        probe.unlink()


def test_real_tree_passes_import_linter() -> None:
    subprocess.run([str(Path(sys.executable).with_name("lint-imports")), "--no-cache"], cwd=ROOT, capture_output=True, check=True)

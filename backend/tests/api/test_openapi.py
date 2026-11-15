import json
import subprocess
import sys
from pathlib import Path

from lumiere.main import create_app
from tests.api.conftest import Api


def test_openapi_search_only_has_200_and_500(api: Api) -> None:
    document = create_app(api.services).openapi()
    assert document["info"]["title"] == "Lumiere"
    assert set(document["paths"]["/api/v1/people/search"]["get"]["responses"]) == {"200", "500"}


def test_export_is_inert_and_deterministic() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/export_openapi.py"
    subprocess.run([sys.executable, str(script)], check=True, env={"PATH": str(Path(sys.executable).parent)})
    contract = script.parents[2] / "openapi.json"
    first = contract.read_bytes()
    subprocess.run([sys.executable, str(script)], check=True, env={"PATH": str(Path(sys.executable).parent)})
    assert contract.read_bytes() == first
    assert json.loads(first)["info"]["title"] == "Lumiere"

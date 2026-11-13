"""Regenerate the public API JSON Schema; run with npm run contract."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from wayfinder.schemas import SearchResponse

Path("client/api.schema.json").write_text(
    json.dumps(SearchResponse.model_json_schema(), indent=2) + "\n"
)

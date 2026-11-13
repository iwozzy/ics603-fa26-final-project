"""Regenerate the public API JSON Schema; run with npm --prefix frontend run contract."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lumiere.schemas import SearchResponse

schema = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api.schema.json"
schema.write_text(json.dumps(SearchResponse.model_json_schema(), indent=2) + "\n")

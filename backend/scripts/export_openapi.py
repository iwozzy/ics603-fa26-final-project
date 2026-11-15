"""Export with inert services; no settings, clients, or sessions are constructed."""
import json
from pathlib import Path
from typing import cast

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.application.ports.search import PeopleSearch
from lumiere.application.ports.sessions import GuestSessions
from lumiere.main import create_app


def export() -> None:
    services = HttpServices(cast(PeopleSearch, None), cast(GuestSessions, None), b"")
    document = create_app(services).openapi()
    path = Path(__file__).resolve().parents[2] / "openapi.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    export()

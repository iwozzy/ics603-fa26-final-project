"""Export without starting the lifespan, contacting providers, or telemetry."""

import json
import sys

from lumiere.bootstrap import create_app
from lumiere.config import Settings

json.dump(create_app(Settings(telemetry_enabled=False)).openapi(), sys.stdout, indent=2)
sys.stdout.write("\n")

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


def test_openapi_timeline_contract(api: Api) -> None:
    document = create_app(api.services).openapi()
    operation = document['paths']['/api/v1/timeline']['get']
    assert operation['operationId'] == 'listTimeline'
    assert set(operation['responses']) == {'200', '500'}
    assert 'content' not in operation['responses']['500']
    schemas = document['components']['schemas']
    page = schemas['TimelineResponse']
    assert set(page['required']) == {'items', 'older_cursor', 'newer_cursor', 'as_of', 'anchor_index'}
    movie = schemas[page['properties']['items']['items']['$ref'].rsplit('/', 1)[1]]
    movie_id = movie['properties']['id']
    assert movie_id['type'] == 'integer'
    assert movie_id['minimum'] == 1
    assert movie_id['maximum'] == 9007199254740991
    assert movie['properties']['release_date']['format'] == 'date'
    for name, field_type in (('overview', 'string'), ('poster_image_url', 'string')):
        assert {schema['type'] for schema in movie['properties'][name]['anyOf']} == {field_type, 'null'}
    for name, field_type in (('older_cursor', 'string'), ('newer_cursor', 'string'), ('as_of', 'string'), ('anchor_index', 'integer')):
        assert {schema['type'] for schema in page['properties'][name]['anyOf']} == {field_type, 'null'}
    parameters = {parameter['name']: parameter['schema'] for parameter in operation['parameters']}
    assert set(parameters) == {'limit', 'cursor', 'direction', 'anchor_date', 'anchor_id'}
    assert parameters['limit']['default'] == 20
    assert parameters['limit']['minimum'] == 1
    assert parameters['limit']['maximum'] == 100


def test_export_is_inert_and_deterministic() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/export_openapi.py"
    guard = """
import runpy
import sys

class NoRuntimeImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'lumiere.bootstrap', 'lumiere.config'}:
            raise AssertionError('OpenAPI export imported runtime composition or settings')

sys.meta_path.insert(0, NoRuntimeImports())
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    command = [sys.executable, "-c", guard, str(script)]
    sandbox_env = {"PATH": str(Path(sys.executable).parent)}
    subprocess.run(command, check=True, env=sandbox_env)
    contract = script.parents[2] / "openapi.json"
    first = contract.read_bytes()
    subprocess.run(command, check=True, env=sandbox_env)
    assert contract.read_bytes() == first
    assert json.loads(first)["info"]["title"] == "Lumiere"

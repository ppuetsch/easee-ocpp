"""Generate the Easee cloud API client used by the integration from Easee's OpenAPI specification.

The specification (openapi/easee-cloud-api.json, downloaded from
https://developer.easee.com/openapi/easee-cloud-api.json) covers the whole cloud API. The
integration needs only a handful of operations, so this script

1. keeps only the operations listed in OPERATIONS (plus the schemas they reference),
2. applies SCHEMA_FIXES and PATH_FIXES – corrections where the specification does not match the API,
3. runs openapi-python-client and places the package at
   custom_components/easee_ocpp/easee_cloud_client (not committed; built in CI and for tests).

    python scripts/generate_easee_client.py            # use the pinned specification
    python scripts/generate_easee_client.py --download # refresh the pinned specification first
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import urllib.request

type JsonObject = dict[str, Any]

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SPECIFICATION = REPOSITORY_ROOT / "openapi" / "easee-cloud-api.json"
GENERATOR_CONFIG = REPOSITORY_ROOT / "openapi" / "generator-config.yaml"
TARGET_PACKAGE = REPOSITORY_ROOT / "custom_components" / "easee_ocpp" / "easee_cloud_client"
SPECIFICATION_URL = "https://developer.easee.com/openapi/easee-cloud-api.json"
GENERATED_PACKAGE_NAME = "easee_cloud_client"
SCHEMA_REFERENCE_PREFIX = "#/components/schemas/"

# operationId per (method, path) the integration calls.
OPERATIONS: dict[tuple[str, str], str] = {
    ("post", "/api/accounts/login"): "Account_Authenticate",
    ("post", "/api/accounts/refresh_token"): "Account_RefreshToken",
    ("get", "/api/accounts/chargers"): "Account_GetChargerFavorites",
    ("get", "/api/chargers/{chargerId}/config"): "Charger_GetCachedChargerConfig",
    ("get", "/api/chargers/{chargerId}/site"): "Charger_GetChargerSite",
    ("get", "/api/chargers/{chargerId}/partners"): "Charger_GetChargerOperator",
    ("get", "/state/{serialNumber}/observations"): "getobservations",
    ("post", "/api/sites/{siteId}/circuits/{circuitId}/dynamicCurrent"): "Site_SetDynamicCircuitCurrent",
    ("get", "/local-ocpp/v1/connection-details/{serialNumber}"): "GetUserChargerConnectionDetailsEndpoint",
    ("post", "/local-ocpp/v1/connection-details/{serialNumber}"): "PostUserChargerConnectionDetailsEndpoint",
    ("post", "/local-ocpp/v1/connections/chargers/{serialNumber}"): "ApplyOcppForUserChargerEndpoint",
    ("delete", "/local-ocpp/v1/connections/chargers/{serialNumber}"): "DisableOcppForUserChargerEndpoint",
}


def download_specification() -> None:
    """Refresh the pinned copy of Easee's specification."""
    with urllib.request.urlopen(SPECIFICATION_URL) as response:
        SPECIFICATION.write_bytes(response.read())


def load(path: Path) -> JsonObject:
    """Read a JSON document."""
    document: JsonObject = json.loads(path.read_text(encoding="utf-8"))
    return document


def selected_paths(specification: JsonObject) -> JsonObject:
    """Return only the listed operations, failing loudly if Easee renamed or removed one."""
    paths: JsonObject = {}
    for (method, path), operation_id in OPERATIONS.items():
        operation = specification["paths"].get(path, {}).get(method)
        if operation is None:
            raise SystemExit(f"{method.upper()} {path} is missing from the specification")
        if operation.get("operationId") != operation_id:
            raise SystemExit(f"{method.upper()} {path}: operationId changed to {operation.get('operationId')}")
        paths.setdefault(path, {})[method] = operation
    return paths


def referenced_schema_names(node: Any) -> set[str]:
    """Names of all schemas a JSON fragment references directly."""
    if isinstance(node, dict):
        names = {node["$ref"].removeprefix(SCHEMA_REFERENCE_PREFIX)} if "$ref" in node else set()
        for value in node.values():
            names |= referenced_schema_names(value)
        return names
    if isinstance(node, list):
        return set().union(*(referenced_schema_names(item) for item in node)) if node else set()
    return set()


def reachable_schemas(start: Any, schemas: JsonObject) -> JsonObject:
    """Schemas referenced from start, followed transitively."""
    pending = referenced_schema_names(start)
    reachable: JsonObject = {}
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable[name] = schemas[name]
        pending |= referenced_schema_names(schemas[name]) - reachable.keys()
    return reachable


def fix_observation_value(schemas: JsonObject) -> None:
    """Observations are declared abstract without their subtypes, so the value field is missing.

    The API returns e.g. {"id": 80, "timestamp": "...", "dataType": 4, "value": 344}.
    """
    observation = schemas["Current_Device_State_API_Observation"]
    observation["properties"]["value"] = {"description": "Observed value; its type depends on dataType."}


def fix_connection_details_response(paths: JsonObject) -> None:
    """GET connection-details is declared to return only {version}; it returns ConnectionDetailsDto."""
    get_operation = paths["/local-ocpp/v1/connection-details/{serialNumber}"]["get"]
    content = get_operation["responses"]["200"]["content"]["application/json"]
    content["schema"] = {"$ref": SCHEMA_REFERENCE_PREFIX + "Easee_OCPP_Configuration_API_ConnectionDetailsDto"}


SCHEMA_FIXES = (fix_observation_value,)


def fix_empty_ocpp_responses(paths: JsonObject) -> None:
    """Applying and disabling OCPP answer 200 with an empty body, not the declared JSON object."""
    for path, method in (
        ("/local-ocpp/v1/connections/chargers/{serialNumber}", "post"),
        ("/local-ocpp/v1/connections/chargers/{serialNumber}", "delete"),
    ):
        paths[path][method]["responses"]["200"].pop("content", None)


PATH_FIXES = (fix_connection_details_response, fix_empty_ocpp_responses)


def filtered_specification() -> JsonObject:
    """The specification reduced to the operations the integration uses."""
    specification = load(SPECIFICATION)
    paths = selected_paths(specification)
    schemas = specification["components"]["schemas"]
    for schema_fix in SCHEMA_FIXES:
        schema_fix(schemas)
    for path_fix in PATH_FIXES:
        path_fix(paths)
    return {
        "openapi": specification["openapi"],
        "info": specification["info"],
        "servers": specification["servers"],
        "paths": paths,
        "components": {
            "schemas": reachable_schemas(paths, schemas),
            "securitySchemes": specification["components"].get("securitySchemes", {}),
        },
        "security": specification.get("security", []),
    }


def generate(work_directory: Path) -> Path:
    """Run openapi-python-client and return the generated package directory."""
    filtered = work_directory / "easee-cloud-api.filtered.json"
    filtered.write_text(json.dumps(filtered_specification(), indent=1), encoding="utf-8")
    output = work_directory / "client"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "openapi_python_client",
            "generate",
            "--path",
            str(filtered),
            "--config",
            str(GENERATOR_CONFIG),
            "--output-path",
            str(output),
            "--overwrite",
            "--meta",
            "none",
        ],
        check=True,
    )
    return output


def install(package: Path) -> None:
    """Replace the package inside the integration."""
    if TARGET_PACKAGE.exists():
        shutil.rmtree(TARGET_PACKAGE)
    shutil.copytree(package, TARGET_PACKAGE)


def main() -> None:
    """Command line."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--download", action="store_true", help="refresh the pinned specification first")
    arguments = parser.parse_args()
    if arguments.download:
        download_specification()
    with tempfile.TemporaryDirectory() as temporary:
        install(generate(Path(temporary)))
    print(f"Generated {TARGET_PACKAGE.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()

"""The published OpenAPI document must describe what the API really returns."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

PROBLEM = "application/problem+json"
PROBLEM_REF = {"$ref": "#/components/schemas/ProblemDetail"}


@pytest.fixture
def spec(client: TestClient) -> dict[str, Any]:
    """Return the OpenAPI document served by the application."""
    document: dict[str, Any] = client.get("/openapi.json").json()
    return document


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Flatten the document into ``(method, path, operation)`` triples."""
    return [
        (method, path, operation)
        for path, methods in spec["paths"].items()
        for method, operation in methods.items()
    ]


def test_every_operation_has_summary_description_and_response_text(spec: dict[str, Any]) -> None:
    """No endpoint is left with generated placeholder documentation."""
    for method, path, operation in _operations(spec):
        assert operation["summary"], (method, path)
        assert operation["description"], (method, path)
        for status, response in operation["responses"].items():
            assert response["description"] != "Successful Response", (method, path, status)


def test_all_validation_errors_are_problem_documents(spec: dict[str, Any]) -> None:
    """The stock ``HTTPValidationError`` contract must not leak into the schema."""
    schemas = spec["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    for method, path, operation in _operations(spec):
        response = operation["responses"].get("422")
        if response is None:
            continue
        assert response["content"] == {
            PROBLEM: {"schema": PROBLEM_REF, "examples": response["content"][PROBLEM]["examples"]}
        }, (method, path)


def test_documented_error_responses_use_problem_media_type_and_examples(
    spec: dict[str, Any],
) -> None:
    """404, 409 and 422 responses advertise ``application/problem+json`` with an example."""
    create = spec["paths"]["/api/v1/books"]["post"]["responses"]
    get_one = spec["paths"]["/api/v1/books/{book_id}"]["get"]["responses"]

    for response in (create["409"], create["422"], get_one["404"]):
        assert list(response["content"]) == [PROBLEM]
        assert response["content"][PROBLEM]["examples"]


def test_path_and_query_parameters_are_described_with_examples(spec: dict[str, Any]) -> None:
    """Every parameter has a description and an example value."""
    for method, path, operation in _operations(spec):
        for parameter in operation.get("parameters", []):
            assert parameter.get("description"), (method, path, parameter["name"])
            schema = parameter["schema"]
            has_example = "examples" in schema or "example" in parameter or "default" in schema
            assert has_example, (method, path, parameter["name"])


def test_schema_properties_are_described(spec: dict[str, Any]) -> None:
    """Every property of the public models carries a description."""
    schemas = spec["components"]["schemas"]
    for name in ("BookCreate", "BookUpdate", "BookRead", "ProblemDetail", "HealthStatus"):
        for prop, definition in schemas[name]["properties"].items():
            assert definition.get("description"), (name, prop)
    for prop, definition in schemas["Page_BookRead_"]["properties"].items():
        assert definition.get("description"), prop


def test_request_and_response_models_provide_examples(spec: dict[str, Any]) -> None:
    """Swagger UI can pre-fill a valid request and show a realistic response."""
    schemas = spec["components"]["schemas"]

    for name in ("BookCreate", "BookUpdate", "BookRead", "ProblemDetail"):
        assert "example" in schemas[name], name


def test_documented_status_codes_match_reality(spec: dict[str, Any]) -> None:
    """Spot-check that documented codes cover the codes the API actually returns."""
    book = spec["paths"]["/api/v1/books/{book_id}"]

    assert set(book["get"]["responses"]) == {"200", "404", "422"}
    assert set(book["patch"]["responses"]) == {"200", "404", "409", "422"}
    assert set(book["delete"]["responses"]) == {"204", "404", "422"}

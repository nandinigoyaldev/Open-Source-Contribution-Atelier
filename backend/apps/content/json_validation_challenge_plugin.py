"""
JSON validation challenge lesson plugin.

Validates a user-submitted JSON document against a lightweight schema.
This is a deliberate SUBSET of JSON Schema (type, required, properties,
items, enum, minimum/maximum, minLength/maxLength) — not full-spec
compliant (no $ref, oneOf/anyOf/allOf, or format validators). Chosen to
avoid adding a new dependency (jsonschema package) for what these lesson
exercises need; documented here explicitly as an intentional scope
boundary, not an oversight.
"""

import json
from typing import Any, Dict, List, Tuple

from .plugins import LessonPlugin, registry


_TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def _validate_against_schema(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """
    Recursively validate value against schema. Returns a list of
    human-readable error messages (empty list means valid).
    """
    errors: List[str] = []

    expected_type = schema.get("type")
    if expected_type is not None:
        py_type = _TYPE_MAP.get(expected_type)
        if py_type is None:
            errors.append(f"{path}: unknown schema type '{expected_type}'")
        elif expected_type == "integer" and isinstance(value, bool):
            # bool is a subclass of int in Python — explicitly exclude it
            # from matching "integer", since a boolean isn't a JSON integer.
            errors.append(f"{path}: expected integer, got boolean")
        elif not isinstance(value, py_type):
            errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
            return errors  # further checks on this path aren't meaningful with wrong type

    if "enum" in schema:
        if value not in schema["enum"]:
            errors.append(f"{path}: value {value!r} not in allowed enum {schema['enum']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum {schema['maximum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: length {len(value)} is below minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: length {len(value)} is above maxLength {schema['maxLength']}")

    if isinstance(value, dict) and "properties" in schema:
        properties = schema["properties"]
        required = schema.get("required", [])

        for req_key in required:
            if req_key not in value:
                errors.append(f"{path}: missing required property '{req_key}'")

        for key, sub_value in value.items():
            if key in properties:
                errors.extend(
                    _validate_against_schema(sub_value, properties[key], f"{path}.{key}")
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected additional property '{key}'")

    if isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for i, item in enumerate(value):
            errors.extend(_validate_against_schema(item, item_schema, f"{path}[{i}]"))

    return errors


class JSONValidationChallengePlugin(LessonPlugin):
    """
    Lesson plugin for JSON-structure-writing challenges.

    Expected submission data shape:
    {
        "submitted_json": "{\\"name\\": \\"Alice\\", \\"age\\": 30}",
        "schema": {
            "type": "object",
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "age": {"type": "integer", "minimum": 0}
            }
        }
    }
    """

    identifier = "json_validation_challenge"
    version = "1.0"
    name = "JSON Validation Challenge"
    description = (
        "Write a JSON document matching a given schema (a lightweight, "
        "dependency-free JSON Schema subset), scored by percentage of "
        "schema constraints satisfied."
    )

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        submitted = data.get("submitted_json")
        if not isinstance(submitted, str) or not submitted.strip():
            return False

        schema = data.get("schema")
        if not isinstance(schema, dict):
            return False

        try:
            json.loads(submitted)
        except json.JSONDecodeError:
            return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        try:
            parsed = json.loads(data["submitted_json"])
        except json.JSONDecodeError:
            return 0.0

        schema = data["schema"]
        errors = _validate_against_schema(parsed, schema)

        if not errors:
            return 100.0

        # Partial credit proportional to how many top-level required
        # properties (the most common and heaviest-weighted mistake) are
        # actually present, as a rough signal beyond binary pass/fail.
        required = schema.get("required", []) if isinstance(parsed, dict) else []
        if required:
            present = sum(1 for key in required if isinstance(parsed, dict) and key in parsed)
            structural_score = (present / len(required)) * 60.0
        else:
            structural_score = 0.0

        return round(structural_score, 2)

    @classmethod
    def get_validation_errors(cls, data: Dict[str, Any]) -> List[str]:
        """Non-interface helper: returns human-readable validation errors for learner feedback."""
        if not cls.validate_submission(data):
            return ["Submission is not valid JSON or is missing required fields."]
        parsed = json.loads(data["submitted_json"])
        return _validate_against_schema(parsed, data["schema"])


registry.register(JSONValidationChallengePlugin)

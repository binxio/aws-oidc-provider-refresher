from aws_oidc_provider_refresher.logger import log
from jsonschema.exceptions import ValidationError
from jsonschema import validators, Draft7Validator, FormatChecker, validators


schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verbose": {
            "type": "boolean",
            "description": "if you want more output",
            "default": False,
        },
        "dry_run": {
            "type": "boolean",
            "description": "if you only want output",
            "default": False,
        },
        "append": {
            "type": "boolean",
            "description": "fingerprints to the list",
            "default": False,
        },
        "max_thumbprints": {
            "type": "integer",
            "minimum": 0,
            "description": "to keep in the list, 0 means unlimited",
            "default": 0,
        },
        "tags": {
            "type": "array",
            "description": "to select OIDC providers with",
            "items": {"type": "string"},
            "default": [],
        },
    },
}


def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema,
        ):
            yield error

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


validator = extend_with_default(Draft7Validator)(schema, format_checker=FormatChecker())


def validate(request: dict) -> bool:
    """
    return True and completes the missing values if the dictionary matches the schema, otherwise False.
    >>> x = {}
    >>> validate(x)
    True
    >>> print(x)
    {'verbose': False, 'dry_run': False, 'append': False, 'max_thumbprints': 0, 'tags': []}
    >>> validate({'max_thumbprints': -1})
    False
    >>> x = {'verbose': True, 'dry_run': True, 'max_thumbprints': 3, 'tags': ["auto-refresh=true"]}
    >>> validate(x)
    True
    >>> print(x)
    {'verbose': True, 'dry_run': True, 'max_thumbprints': 3, 'tags': [{'Name': 'auto-refresh', 'Values': ['true']}], 'append': False}

    """
    try:
        validator.validate(request)
        return True
    except ValidationError as e:
        log.error("invalid request received: %s" % str(e.message))
        return False

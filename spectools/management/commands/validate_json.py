from django.core.management.base import BaseCommand
from spectools.models import ExampleDocument
from spectools.utils.jsonschema import make_json_schema
import json
try:
    from jsonschema import validate
    from jsonschema.exceptions import ValidationError, SchemaError
    from jsonschema.validators import validator_for, Draft202012Validator
except ImportError:
    print('Error: Missing jsonschema library. Run "pip install jsonschema"')

def validate_json_schema(schema):
    try:
        ValidatorClass = validator_for(schema)
        ValidatorClass.check_schema(schema)
    except Exception as e:
        print(f'JSON schema validation failed: {e.message}')
        return False
    else:
        print('JSON schema validated properly')
        return True

def validate_example_docs(schema):
    ValidatorClass = validator_for(schema)
    validator = ValidatorClass(schema)
    passes = 0
    failures = 0
    name_width = max(len(name) for name in ExampleDocument.objects.values_list('name', flat=True)) + 2
    for doc in ExampleDocument.objects.order_by('name'):
        name_plus_dots = doc.name + ((name_width - len(doc.name)) * '.')
        try:
            validator.validate(
                json.loads(doc.get_document_text())
            )
        except SchemaError as e:
            failures += 1
            print(f'{name_plus_dots} FAIL: error in the JSON Schema itself')
        except ValidationError as e:
            failures += 1
            print(f'{name_plus_dots} FAIL: {e.message}')
        else:
            passes += 1
            print(f'{name_plus_dots} pass')
    print(f'\n{passes} passed, {failures} failed')

class Command(BaseCommand):
    help = 'Validates all example documents against the JSON Schema, printing a report to stdout.'

    def handle(self, **options):
        schema = make_json_schema()
        schema_is_valid = validate_json_schema(schema)
        if schema_is_valid:
            validate_example_docs(schema)

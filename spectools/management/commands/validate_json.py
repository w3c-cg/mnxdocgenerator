from django.core.management.base import BaseCommand
from spectools.models import ExampleDocument
from spectools.utils.jsonschema import make_json_schema
import json
try:
    from jsonschema import validate
    from jsonschema.exceptions import ValidationError, SchemaError
    from jsonschema.validators import validator_for, Draft202012Validator
except ImportError:
    raise ImportError('Error: Missing jsonschema library. Run "pip install jsonschema"') from None

def validate_our_schema():
    schema = make_json_schema()
    if '$schema' not in schema:
        raise ValidationError('"$schema" is a required property')

    try:
        ValidatorClass = validator_for(schema)
        ValidatorClass.check_schema(schema)

    except ValidationError as e:
        print(f'MNX JSON schema failed: {e.message}')
    else:
        print('JSON schema validated properly')

def validate_example_docs():
    schema = make_json_schema()
    ValidatorClass = validator_for(schema)
    validator = ValidatorClass(schema)
    passes = 0
    failures = 0
    name_width = max(len(name) for name in ExampleDocument.objects.values_list('name', flat=True)) + 2
    for doc in ExampleDocument.objects.order_by('name'):
        name_plus_dots = doc.name + ((name_width - len(doc.name)) * '.')
        try:
            doc_parsed = json.loads(doc.get_document_text())
            validator.validate(doc_parsed)
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
        validate_our_schema()
        validate_example_docs()

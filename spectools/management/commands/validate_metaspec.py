"""
Checks that the metaspec files are structurally sound.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from spectools import metaspec as ms
import json
import os
import sys

# The fields every object definition may use, plus the extra ones allowed
# for each kind.
COMMON_OBJECT_FIELDS = {'kind', 'title', 'description', 'role', 'extraJSONSchema'}
KIND_FIELDS = {
    ms.KIND_DICT: {'properties', 'globalAttributes'},
    ms.KIND_ARRAY: {'items', 'minItems', 'maxItems'},
    ms.KIND_KEYED_DICT: {'values'},
    ms.KIND_STRING: {'values', 'pattern'},
    ms.KIND_NUMBER: {'values'},
    ms.KIND_BOOLEAN: set(),
}

# The JSON Schema keywords the generator produces itself, per kind. An
# "extraJSONSchema" that sets one of these silently overrides it, so it's
# worth pointing out.
GENERATED_JSON_SCHEMA_KEYS = {
    ms.KIND_DICT: {
        'type', 'properties', 'required', 'allOf', 'unevaluatedProperties',
    },
    ms.KIND_ARRAY: {'type', 'items', 'minItems', 'maxItems'},
    ms.KIND_KEYED_DICT: {'type', 'additionalProperties', 'patternProperties'},
    ms.KIND_STRING: {'type', 'pattern', 'enum'},
    ms.KIND_NUMBER: {'type', 'enum'},
    ms.KIND_BOOLEAN: {'type'},
}

# The same, for an attribute, keyed by how it gives its type. An attribute
# pointing at a named object is generated as a bare "$ref"; the others are
# generated in full.
GENERATED_ATTRIBUTE_KEYS = {
    'type': {'$ref', 'type'},
    'items': {'type', 'items'},
    'const': {'type', 'const'},
}

ATTRIBUTE_TYPE_FIELDS = ('type', 'items', 'const')
ATTRIBUTE_FIELDS = set(ATTRIBUTE_TYPE_FIELDS) | {
    'required', 'description', 'extraJSONSchema',
}

TOP_LEVEL_FIELDS = {'version', 'format', 'site', 'objects', 'pageCollections'}
SITE_FIELDS = {'siteName', 'formatName', 'sidebarHtml'}
COLLECTION_FIELDS = {'title', 'url', 'pages'}
PAGE_FIELDS = {'title', 'url', 'contentFile'}
EXAMPLE_FIELDS = {
    'slug', 'name', 'blurb', 'documentPath', 'imagePath', 'featured', 'comparisons',
}
COMPARISON_FIELDS = {'format', 'position', 'documentPath', 'preamble'}

class Validator:
    def __init__(self, source_dir, media_dir):
        self.source_dir = source_dir
        self.media_dir = media_dir
        self.errors = []
        self.warnings = []

    def error(self, where, message):
        self.errors.append(f'{where}: {message}')

    def warn(self, where, message):
        self.warnings.append(f'{where}: {message}')

    # -- Generic field checks ---------------------------------------------

    def check_fields(self, where, data, allowed, required=()):
        if not isinstance(data, dict):
            self.error(where, f'should be a dictionary, not {type(data).__name__}.')
            return False
        for key in sorted(set(data) - set(allowed)):
            self.error(where, f'unknown field "{key}".')
        for key in required:
            if key not in data:
                self.error(where, f'missing required field "{key}".')
        return True

    def check_prose(self, where, data):
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            self.error(where, 'should be a list of strings, one per line of text.')

    def check_string(self, where, data):
        if not isinstance(data, str):
            self.error(where, f'should be a string, not {type(data).__name__}.')

    def check_bool(self, where, data):
        if not isinstance(data, bool):
            self.error(where, f'should be true or false, not {data!r}.')

    def check_url(self, where, data):
        if not isinstance(data, str) or not data.startswith('/') or not data.endswith('/'):
            self.error(where, f'{data!r} should be a path starting and ending with a slash.')

    def check_file(self, where, path, directory):
        if not isinstance(path, str):
            self.error(where, f'should be a string, not {type(path).__name__}.')
        elif not os.path.exists(os.path.join(directory, path)):
            self.error(where, f'the file "{path}" does not exist in {directory}.')

    # -- mnx-metaspec.json ------------------------------------------------

    def check_metaspec(self, data):
        if not self.check_fields(
            'mnx-metaspec.json', data, TOP_LEVEL_FIELDS,
            required=('version', 'format', 'site', 'objects')
        ):
            return
        version = data.get('version')
        if not isinstance(version, (int, str)) or isinstance(version, bool):
            self.error('version', f'should be a number or a string, not {version!r}.')
        if self.check_fields('format', data.get('format', {}), {'name', 'slug'},
                required=('name', 'slug')):
            self.check_string('format.name', data['format'].get('name'))
            self.check_string('format.slug', data['format'].get('slug'))
        if self.check_fields('site', data.get('site', {}), SITE_FIELDS,
                required=('siteName', 'formatName')):
            self.check_string('site.siteName', data['site'].get('siteName'))
            self.check_string('site.formatName', data['site'].get('formatName'))
            self.check_prose('site.sidebarHtml', data['site'].get('sidebarHtml', []))

        objects = data.get('objects')
        if not isinstance(objects, dict):
            self.error('objects', 'should be a dictionary mapping slug to definition.')
            return
        for slug, obj in objects.items():
            self.check_object(slug, obj, objects)
        for role in (ms.ROLE_ROOT, ms.ROLE_GLOBAL_ATTRS):
            matches = [
                s for s, o in objects.items()
                if isinstance(o, dict) and o.get('role') == role
            ]
            if len(matches) != 1:
                self.error(
                    'objects',
                    f'exactly one object must have "role": "{role}"; '
                    f'found {len(matches)} ({", ".join(matches) or "none"}).'
                )

        self.check_page_collections(data.get('pageCollections', []))

    def check_object(self, slug, obj, objects):
        where = f'object "{slug}"'
        kind = obj.get('kind') if isinstance(obj, dict) else None
        if kind not in KIND_FIELDS:
            self.error(where, f'has an unknown kind {kind!r}. Valid kinds: '
                f'{", ".join(sorted(KIND_FIELDS))}.')
            return
        if not self.check_fields(where, obj, COMMON_OBJECT_FIELDS | KIND_FIELDS[kind],
                required=('kind',)):
            return
        if 'title' in obj:
            self.check_string(f'{where} title', obj['title'])
        if 'description' in obj:
            self.check_prose(f'{where} description', obj['description'])
        if 'role' in obj and obj['role'] not in (ms.ROLE_ROOT, ms.ROLE_GLOBAL_ATTRS):
            self.error(where, f'has an unknown role {obj["role"]!r}.')
        if 'extraJSONSchema' in obj:
            self.check_extra_json_schema(
                where, obj['extraJSONSchema'], GENERATED_JSON_SCHEMA_KEYS[kind], 'object'
            )

        if kind == ms.KIND_DICT:
            if 'globalAttributes' in obj:
                self.check_bool(f'{where} globalAttributes', obj['globalAttributes'])
            properties = obj.get('properties', {})
            if not isinstance(properties, dict):
                self.error(f'{where} properties', 'should be a dictionary.')
            else:
                for key, attribute in properties.items():
                    self.check_attribute(f'{where} attribute "{key}"', attribute, objects)
        elif kind == ms.KIND_ARRAY:
            self.check_items(where, obj.get('items'), objects)
            for key in ('minItems', 'maxItems'):
                if key in obj and not isinstance(obj[key], int):
                    self.error(f'{where} {key}', f'should be an integer, not {obj[key]!r}.')
            if isinstance(obj.get('minItems'), int) and isinstance(obj.get('maxItems'), int) \
                    and obj['minItems'] > obj['maxItems']:
                self.error(where, 'minItems is greater than maxItems.')
        elif kind == ms.KIND_KEYED_DICT:
            if 'values' not in obj:
                self.error(where, 'needs a "values" field naming the type of every value.')
            else:
                self.check_slug(f'{where} values', obj['values'], objects)
        elif kind in (ms.KIND_STRING, ms.KIND_NUMBER):
            if 'pattern' in obj:
                self.check_string(f'{where} pattern', obj['pattern'])
            self.check_enum_values(where, kind, obj.get('values'))

    def check_extra_json_schema(self, where, extra, generated_keys, what):
        where = f'{where} extraJSONSchema'
        if not isinstance(extra, dict):
            self.error(where, 'should be a dictionary of JSON Schema keywords.')
            return
        if not extra:
            self.error(where, 'is empty; leave it out instead.')
            return
        for key in sorted(k for k in extra if k in generated_keys):
            self.warn(where, f'sets "{key}", which overrides what the generator '
                f'produces for this {what}.')

    def check_enum_values(self, where, kind, values):
        if values is None:
            return
        if not isinstance(values, dict):
            self.error(f'{where} values', 'should be a dictionary mapping value to description.')
            return
        for name, description in values.items():
            self.check_prose(f'{where} value "{name}"', description)
            if kind == ms.KIND_NUMBER:
                try:
                    int(name)
                except ValueError:
                    self.error(
                        f'{where} value "{name}"',
                        'is not a whole number. Values of a "number" object must be.'
                    )

    def check_attribute(self, where, attribute, objects):
        if not self.check_fields(where, attribute, ATTRIBUTE_FIELDS):
            return
        given = [f for f in ATTRIBUTE_TYPE_FIELDS if f in attribute]
        if len(given) != 1:
            self.error(where, 'needs exactly one of "type", "items" or "const"; '
                f'found {", ".join(given) or "none"}.')
        if 'type' in attribute:
            self.check_slug(where, attribute['type'], objects)
        if 'items' in attribute:
            self.check_items(where, attribute['items'], objects)
        if 'const' in attribute:
            self.check_string(f'{where} const', attribute['const'])
        if 'required' in attribute:
            self.check_bool(f'{where} required', attribute['required'])
        if 'description' in attribute:
            self.check_prose(f'{where} description', attribute['description'])
        if 'extraJSONSchema' in attribute:
            generated_keys = set()
            for field in given:
                generated_keys |= GENERATED_ATTRIBUTE_KEYS[field]
            self.check_extra_json_schema(
                where, attribute['extraJSONSchema'], generated_keys, 'attribute'
            )

    def check_items(self, where, items, objects):
        if not isinstance(items, list) or not items:
            self.error(f'{where} items', 'should be a non-empty list of object slugs.')
            return
        for slug in items:
            self.check_slug(f'{where} items', slug, objects)

    def check_slug(self, where, slug, objects):
        if not isinstance(slug, str):
            self.error(where, f'should name an object, not {slug!r}.')
        elif slug not in objects:
            self.error(where, f'refers to an unknown object "{slug}".')

    def check_page_collections(self, collections):
        if not isinstance(collections, list):
            self.error('pageCollections', 'should be a list.')
            return
        seen_urls = {}
        for i, collection in enumerate(collections):
            where = f'pageCollections[{i}]'
            if not self.check_fields(where, collection, COLLECTION_FIELDS,
                    required=('title', 'url')):
                continue
            where = f'collection "{collection["title"]}"'
            self.check_url(f'{where} url', collection['url'])
            for j, page in enumerate(collection.get('pages', [])):
                page_where = f'{where} page {j + 1}'
                if not self.check_fields(page_where, page, PAGE_FIELDS,
                        required=('title', 'url', 'contentFile')):
                    continue
                page_where = f'page "{page["title"]}"'
                self.check_url(f'{page_where} url', page['url'])
                self.check_file(
                    f'{page_where} contentFile', page['contentFile'],
                    os.path.join(self.source_dir, ms.CONTENT_DIRNAME)
                )
                if page['url'] in seen_urls:
                    self.error(page_where, f'has the same URL as "{seen_urls[page["url"]]}".')
                seen_urls[page['url']] = page['title']

    # -- mnx-examples.json ------------------------------------------------

    def check_examples(self, data):
        if not self.check_fields('mnx-examples.json', data,
                {'comparisonFormats', 'examples'}, required=('examples',)):
            return
        formats = data.get('comparisonFormats', [])
        if not isinstance(formats, list):
            self.error('comparisonFormats', 'should be a list.')
            formats = []
        format_slugs = set()
        for i, doc_format in enumerate(formats):
            if self.check_fields(f'comparisonFormats[{i}]', doc_format, {'name', 'slug'},
                    required=('name', 'slug')):
                format_slugs.add(doc_format['slug'])

        examples = data.get('examples')
        if not isinstance(examples, list):
            self.error('examples', 'should be a list.')
            return
        seen_slugs = set()
        for i, example in enumerate(examples):
            where = f'examples[{i}]'
            if not self.check_fields(where, example, EXAMPLE_FIELDS,
                    required=('slug', 'name', 'documentPath')):
                continue
            where = f'example "{example["slug"]}"'
            self.check_string(f'{where} name', example['name'])
            if example['slug'] in seen_slugs:
                self.error(where, 'is defined more than once.')
            seen_slugs.add(example['slug'])
            self.check_prose(f'{where} blurb', example.get('blurb', []))
            self.check_file(f'{where} documentPath', example['documentPath'], self.media_dir)
            if example.get('imagePath'):
                self.check_file(f'{where} imagePath', example['imagePath'], self.media_dir)
            if 'featured' in example:
                self.check_bool(f'{where} featured', example['featured'])
            for j, comparison in enumerate(example.get('comparisons', [])):
                c_where = f'{where} comparison {j + 1}'
                if not self.check_fields(c_where, comparison, COMPARISON_FIELDS,
                        required=('format', 'position', 'documentPath')):
                    continue
                if comparison['format'] not in format_slugs:
                    self.error(c_where, f'refers to an unknown comparison format '
                        f'"{comparison["format"]}".')
                if not isinstance(comparison['position'], int):
                    self.error(f'{c_where} position', 'should be an integer.')
                self.check_file(f'{c_where} documentPath', comparison['documentPath'],
                    self.media_dir)
                self.check_prose(f'{c_where} preamble', comparison.get('preamble', []))

    # -- Checks that need the loaded graph --------------------------------

    def check_graph(self, metaspec):
        reachable = set()
        def walk(obj):
            if obj in reachable:
                return
            reachable.add(obj)
            for attribute in obj.get_child_relationships(include_global_attrs=True):
                walk(attribute.child)
        walk(metaspec.root_object)
        for obj in metaspec.objects.values():
            # Objects with a role are structural, so they're not expected to
            # be referenced by anything.
            if obj not in reachable and not obj.role:
                self.warn(f'object "{obj.slug}"', 'is not used by any other object.')

    # -- Entry point ------------------------------------------------------

    def run(self):
        metaspec_data = examples_data = None
        for filename, checker in (
            (ms.METASPEC_FILENAME, self.check_metaspec),
            (ms.EXAMPLES_FILENAME, self.check_examples),
        ):
            path = os.path.join(self.source_dir, filename)
            try:
                with open(path, 'r') as fp:
                    data = json.load(fp, object_pairs_hook=ms.reject_duplicate_keys)
            except (IOError, ValueError, ms.MetaspecError) as e:
                self.error(filename, str(e))
                continue
            checker(data)
            if filename == ms.METASPEC_FILENAME:
                metaspec_data = data
            else:
                examples_data = data

        # The graph checks assume the files are structurally sound, so they
        # only run once everything above is clean. Building the graph reads
        # every example document, which is where an example that no longer
        # matches the specification is caught.
        if not self.errors and metaspec_data is not None and examples_data is not None:
            try:
                metaspec = ms.Metaspec(
                    metaspec_data, examples_data, self.source_dir, self.media_dir
                )
            except ms.MetaspecError as e:
                self.error('the specification', str(e))
            else:
                self.check_graph(metaspec)

class Command(BaseCommand):
    help = 'Checks the metaspec files for errors, printing a report to stdout.'

    def handle(self, **options):
        validator = Validator(str(settings.METASPEC_DIR), str(settings.MEDIA_DIR))
        validator.run()
        for warning in validator.warnings:
            print(f'Warning: {warning}')
        for error in validator.errors:
            print(f'Error: {error}')
        if validator.errors:
            print(f'\n{len(validator.errors)} error(s) found.')
            sys.exit(1)
        print(f'\nNo errors found ({len(validator.warnings)} warning(s)).')

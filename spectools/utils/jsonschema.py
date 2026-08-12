from spectools import metaspec as ms

# Each of these types is a native JSON Schema type and is also defined as an
# object in the metaspec, so it's emitted inline instead of as a "$defs" entry.
NATIVE_TYPES = set(['boolean'])

def make_json_schema(schema_slug='mnx'):
    """
    Creates a JSON schema from the metaspec. The result is a Python data
    structure that, if serialized to JSON, is a correct JSON schema.
    """
    metaspec = ms.get_metaspec()
    result = get_schema_for_object(metaspec.root_object)
    result.update({
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': f'https://w3c-cg.github.io/mnx/docs/mnx-schema.json/version/{metaspec.version}',
        'title': 'MNX document',
        'description': 'An encoding of Common Western Music Notation.',
    })

    # Next, add all defs. We do this for every named object except the ones
    # that JSON Schema already has a type for.
    defs = {
        slug: get_schema_for_object(obj, use_defs=False)
        for slug, obj in metaspec.objects.items()
        if slug not in NATIVE_TYPES
    }
    if defs:
        result['$defs'] = defs

    return result

def get_schema_for_object(obj, use_defs=True):
    """
    Given a SpecObject, returns its JSON schema definition as a Python
    dictionary.

    With use_defs=True, named objects are emitted as a "$ref" pointing at
    their "$defs" entry. Objects declared inline in the metaspec -- arrays
    and literal strings -- have no "$defs" entry, so they're always
    emitted in full.
    """
    if obj.slug not in NATIVE_TYPES and use_defs and obj.slug:
        # The object's own keywords, including any "extraJSONSchema", go on
        # its "$defs" entry rather than on each reference to it.
        return {
            '$ref': f'#/$defs/{obj.slug}'
        }
    result = get_inline_schema_for_object(obj)
    result.update(obj.extra_json_schema)
    return result

def get_inline_schema_for_object(obj):
    """
    Returns the JSON schema keywords generated from a SpecObject's kind,
    without its "extraJSONSchema".
    """
    if obj.slug in NATIVE_TYPES:
        return {
            'type': obj.slug
        }
    kind = obj.kind
    if kind == ms.KIND_DICT:
        result = {
            'type': 'object',
            'properties': {
                a.child_key: get_schema_for_object(a.child)
                for a in obj.get_child_relationships()
            },
        }
        required = [a.child_key for a in obj.get_child_relationships() if a.is_required]
        if required:
            result['required'] = list(sorted(required))
        if obj.uses_global_attrs:
            result['allOf'] = [
                {'$ref': f'#/$defs/{obj.metaspec.global_attrs_object.slug}'}
            ]
            result['unevaluatedProperties'] = False
        return result
    elif kind == ms.KIND_KEYED_DICT:
        return {
            'type': 'object',
            'additionalProperties': False,
            'patternProperties': {
                '^.*$': get_schema_for_object(obj.get_child_relationships()[0].child)
            }
        }
    elif kind == ms.KIND_ARRAY:
        attributes = obj.get_child_relationships()
        if len(attributes) == 1:
            items = get_schema_for_object(attributes[0].child)
        else:
            items = {
                'anyOf': [get_schema_for_object(a.child) for a in attributes],
            }
        result = {
            'type': 'array',
            'items': items
        }
        if obj.min_items is not None:
            result['minItems'] = obj.min_items
        if obj.max_items is not None:
            result['maxItems'] = obj.max_items
        return result
    elif kind == ms.KIND_NUMBER:
        result = {
            'type': 'integer'
        }
        if obj.enum_values:
            result['enum'] = [int(e.name) for e in obj.enum_values]
        return result
    elif kind == ms.KIND_BOOLEAN:
        return {
            'type': 'boolean'
        }
    elif kind == ms.KIND_STRING:
        result = {
            'type': 'string'
        }
        if obj.regex:
            result['pattern'] = obj.regex
        if obj.enum_values:
            result['enum'] = [e.name for e in obj.enum_values]
        return result
    elif kind == ms.KIND_LITERAL:
        return {
            'type': 'string',
            'const': obj.description
        }
    raise ms.MetaspecError(f'Unknown kind "{kind}".')

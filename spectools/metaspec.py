"""
Reads the metaspec files (the source of truth for the specification)
into an object graph that's used by views and templates.

See doctools/METASPEC-FORMAT.md for a description of the file format.
"""

from django.conf import settings
from django.urls import reverse
import json
import os

KIND_DICT = 'dict'
KIND_KEYED_DICT = 'keyedDict'
KIND_ARRAY = 'array'
KIND_STRING = 'string'
KIND_NUMBER = 'number'
KIND_BOOLEAN = 'boolean'
KIND_LITERAL = 'literal'

# Kinds that are documented inline, wherever they're used, rather than on
# a page of their own.
KINDS_WITHOUT_DOCS_PAGE = {KIND_ARRAY, KIND_KEYED_DICT, KIND_LITERAL}

PRETTY_KINDS = {
    KIND_DICT: 'Dictionary',
    KIND_KEYED_DICT: 'Dictionary with user-defined keys',
    KIND_ARRAY: 'Array',
    KIND_STRING: 'String',
    KIND_NUMBER: 'Number',
    KIND_BOOLEAN: 'Boolean',
    KIND_LITERAL: 'Literal string',
}

ROLE_ROOT = 'root'
ROLE_GLOBAL_ATTRS = 'globalAttributes'

METASPEC_FILENAME = 'mnx-metaspec.json'
EXAMPLES_FILENAME = 'mnx-examples.json'
CONTENT_DIRNAME = 'content'

def text(lines):
    """
    Converts a metaspec prose field -- a list of lines -- into a string.
    """
    return '\n'.join(lines or [])

class MetaspecError(Exception):
    pass

class Format:
    """
    The format being documented. Templates reach this as
    SpecObject.schema, for historical reasons.
    """
    def __init__(self, name, slug):
        self.name = name
        self.slug = slug

    def __str__(self):
        return self.name

    def reference_url(self):
        return reverse('reference_homepage', args=(self.slug,))

    def examples_url(self):
        return reverse('example_list', args=(self.slug,))

    def json_objects_url(self):
        return reverse('json_object_list', args=(self.slug,))

class Site:
    """
    Site-wide configuration. Attribute names match what the templates
    expect of SITE_OPTIONS.
    """
    def __init__(self, data):
        self.site_name = data['siteName']
        self.xml_format_name = data['formatName']
        self.sidebar_html = text(data.get('sidebarHtml'))

    def __str__(self):
        return self.site_name

class Attribute:
    """
    One attribute of an object: the key it appears under, the object
    describing its value, and whether it's required.
    """
    def __init__(self, parent, key, child, is_required=False, description='',
            extra_json_schema=None):
        self.parent = parent
        self.child_key = key
        self.child = child
        self.is_required = is_required
        self.description = description
        # Raw JSON Schema keywords, merged into this attribute's generated
        # schema as-is. Unlike a SpecObject's, these apply to this one use
        # of the type rather than to every use of it.
        self.extra_json_schema = extra_json_schema or {}

    def __repr__(self):
        return f'<Attribute parent="{self.parent.name}" key="{self.child_key}">'

class EnumValue:
    def __init__(self, parent, name, description=''):
        self.parent = parent
        self.name = name
        self.description = description

    def __str__(self):
        return self.name

    def pretty_name(self):
        if self.parent.kind == KIND_STRING:
            return f'"{self.name}"'
        return self.name

class SpecObject:
    """
    One object in the specification: a dictionary, array, string, number,
    boolean, literal or user-keyed dictionary.

    Objects declared inline -- an "items" list or a "const" on an
    attribute -- are anonymous: they have no slug, no name and no
    documentation page of their own.
    """
    def __init__(self, metaspec, slug=None, kind=KIND_DICT, title=None,
            description='', uses_global_attrs=True, regex='', role=None,
            extra_json_schema=None):
        self.metaspec = metaspec
        self.slug = slug
        self.kind = kind
        self.name = title or slug
        self.description = description
        self.uses_global_attrs = uses_global_attrs
        self.regex = regex
        self.role = role
        # Raw JSON Schema keywords, merged into this object's generated
        # schema definition as-is.
        self.extra_json_schema = extra_json_schema or {}

        # Populated as the graph is built.
        self.attributes = []      # Attributes of this object.
        self.enum_values = []     # Allowed values, for strings and numbers.
        self.parent_attributes = []  # Attributes elsewhere that point here.

    def __str__(self):
        return self.name or f'<anonymous {self.kind}>'

    @property
    def schema(self):
        # Templates refer to this as "schema".
        return self.metaspec.format

    def get_absolute_url(self):
        return reverse('json_object_detail', args=(self.schema.slug, self.slug))

    def has_docs_page(self):
        return self.kind not in KINDS_WITHOUT_DOCS_PAGE

    def is_array(self):
        return self.kind == KIND_ARRAY

    def is_literal_string(self):
        return self.kind == KIND_LITERAL

    def is_user_defined_dict(self):
        return self.kind == KIND_KEYED_DICT

    def is_global_attrs_object(self):
        return self.role == ROLE_GLOBAL_ATTRS

    def docs_page_title(self):
        if self.is_global_attrs_object():
            return 'Global attributes'
        return f'The {self.name} object'

    def pretty_object_type(self):
        return PRETTY_KINDS[self.kind]

    def get_child_relationships(self, include_global_attrs=False):
        result = list(self.attributes)
        if include_global_attrs:
            global_attrs = self.get_global_child_relationships()
            if global_attrs:
                result += global_attrs
                result.sort(key=lambda x: x.child_key)
        return result

    def get_global_child_relationships(self):
        if self.kind == KIND_DICT and self.uses_global_attrs:
            return list(self.metaspec.global_attrs_object.attributes)
        return []

    def get_parent_relationships(self):
        """
        Returns the attributes that point at this object, for the "Parent
        objects" section of its docs page.

        Where an object is reached through something undocumented -- an
        array, say -- the array's own parent attribute is reported
        instead, since that's what a reader can navigate to.
        """
        global_attrs = self.metaspec.global_attrs_object
        result = []
        for attribute in self.parent_attributes:
            if attribute.parent is global_attrs:
                continue
            if attribute.parent.has_docs_page():
                result.append(attribute)
            elif attribute.parent.parent_attributes:
                result.append(attribute.parent.parent_attributes[0])
        result.sort(key=lambda a: (a.parent.name, a.child_key))
        return result

    def matches_json(self, json_data):
        """
        Returns True if this object appears to describe the given JSON
        data. Only looks one level deep.
        """
        if self.kind == KIND_DICT:
            keys = {a.child_key for a in self.get_child_relationships(include_global_attrs=True)}
            return all(k in keys for k in json_data.keys())
        elif self.kind == KIND_KEYED_DICT:
            return isinstance(json_data, dict)
        elif self.kind == KIND_ARRAY:
            return isinstance(json_data, list)
        elif self.kind in (KIND_STRING, KIND_LITERAL):
            return isinstance(json_data, str)
        elif self.kind == KIND_NUMBER:
            return isinstance(json_data, (int, float))
        elif self.kind == KIND_BOOLEAN:
            return isinstance(json_data, bool)
        raise NotImplementedError(self.kind)

def get_object_for_data(json_data, object_def_list):
    """
    Given JSON data and the objects that might describe it, returns the
    one that does.
    """
    if len(object_def_list) == 1:
        return object_def_list[0] # Common case.
    for object_def in object_def_list:
        if object_def.matches_json(json_data):
            return object_def
    raise MetaspecError(
        'None of these objects describe the data {!r}: {}'.format(
            json_data,
            ', '.join(str(o) for o in object_def_list)
        )
    )

class Page:
    def __init__(self, collection, data, content_dir):
        self.collection = collection
        self.title = data['title']
        self.url = data['url']
        self.content_file = data['contentFile']
        self.content_path = os.path.join(content_dir, self.content_file)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.url

    @property
    def content(self):
        with open(self.content_path, 'r') as fp:
            return fp.read()

class PageCollection:
    def __init__(self, data, content_dir):
        self.title = data['title']
        self.url = data['url']
        self.pages = [Page(self, p, content_dir) for p in data.get('pages', [])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.url

class ComparisonFormat:
    def __init__(self, data):
        self.name = data['name']
        self.slug = data['slug']

    def __str__(self):
        return self.name

    def comparison_url(self):
        return reverse('format_comparison_detail', args=(self.slug,))

class Comparison:
    """
    The same example encoded in another format, shown side by side.
    """
    def __init__(self, example, doc_format, data, media_dir):
        self.example = example
        self.doc_format = doc_format
        self.position = data['position']
        self.preamble = text(data.get('preamble'))
        self.document_path = os.path.join(media_dir, data['documentPath'])

    def get_absolute_url(self):
        return self.doc_format.comparison_url() + f'#{self.example.slug}'

    def get_document_text(self):
        with open(self.document_path, 'r') as fp:
            return fp.read()

    def preamble_html(self):
        if self.preamble:
            return '\n'.join(
                f'<p class="examplenotes">{line}</p>'
                for line in self.preamble.split('\n') if line
            )
        return ''

class Example:
    def __init__(self, metaspec, data, media_dir):
        self.metaspec = metaspec
        self.slug = data['slug']
        self.name = data['name']
        self.blurb = text(data.get('blurb'))
        self.document_path = os.path.join(media_dir, data['documentPath'])
        self.image_url = settings.STATIC_URL + data['imagePath'] if data.get('imagePath') else ''
        self.is_featured = data.get('featured', False)
        self.comparisons = []
        # The objects this example uses, worked out by reading it.
        self.spec_objects = set()

    def __str__(self):
        return self.name

    @property
    def schema(self):
        return self.metaspec.format

    def get_absolute_url(self):
        return reverse('example_detail', args=(self.schema.slug, self.slug))

    def get_document_text(self):
        with open(self.document_path, 'r') as fp:
            return fp.read()

class Metaspec:
    """
    The whole specification, loaded from the metaspec files.
    """
    def __init__(self, data, examples_data, source_dir, media_dir):
        self.version = data['version']
        self.format = Format(data['format']['name'], data['format']['slug'])
        self.site = Site(data['site'])

        self.objects = {}
        self.root_object = None
        self.global_attrs_object = None
        self._build_objects(data['objects'])

        content_dir = os.path.join(source_dir, CONTENT_DIRNAME)
        self.page_collections = [
            PageCollection(c, content_dir) for c in data.get('pageCollections', [])
        ]
        self.pages = [p for c in self.page_collections for p in c.pages]

        self.comparison_formats = {}
        self.examples = []
        self._build_examples(examples_data, media_dir)

    # -- Objects ----------------------------------------------------------

    def _build_objects(self, objects_data):
        # Two passes, because attributes refer to objects by slug and
        # those references may point forward.
        for slug, obj_data in objects_data.items():
            obj = SpecObject(
                metaspec=self,
                slug=slug,
                kind=obj_data['kind'],
                title=obj_data.get('title'),
                description=text(obj_data.get('description')),
                uses_global_attrs=obj_data.get('globalAttributes', True),
                regex=obj_data.get('pattern', ''),
                role=obj_data.get('role'),
                extra_json_schema=obj_data.get('extraJSONSchema'),
            )
            self.objects[slug] = obj
            if obj.role == ROLE_ROOT:
                self.root_object = obj
            elif obj.role == ROLE_GLOBAL_ATTRS:
                self.global_attrs_object = obj

        if self.root_object is None:
            raise MetaspecError(f'No object has "role": "{ROLE_ROOT}".')
        if self.global_attrs_object is None:
            raise MetaspecError(f'No object has "role": "{ROLE_GLOBAL_ATTRS}".')

        for slug, obj_data in objects_data.items():
            self._build_object_children(self.objects[slug], obj_data)

    def _build_object_children(self, obj, obj_data):
        if obj.kind == KIND_DICT:
            for key, attr_data in obj_data.get('properties', {}).items():
                self._add_attribute(
                    obj, key, self._resolve_attribute_type(attr_data, key),
                    is_required=attr_data.get('required', False),
                    description=text(attr_data.get('description')),
                    extra_json_schema=attr_data.get('extraJSONSchema'),
                )
        elif obj.kind == KIND_ARRAY:
            self._add_array_items(obj, obj_data.get('items', []))
        elif obj.kind == KIND_KEYED_DICT:
            self._add_attribute(obj, '0', self._get_object(obj_data['values']))
        elif obj.kind in (KIND_STRING, KIND_NUMBER):
            for name, description in (obj_data.get('values') or {}).items():
                obj.enum_values.append(EnumValue(obj, name, text(description)))

    def _resolve_attribute_type(self, attr_data, key):
        """
        Returns the object describing an attribute's value, creating an
        anonymous one for an inline "items" list or "const".
        """
        if 'const' in attr_data:
            return SpecObject(
                metaspec=self, kind=KIND_LITERAL, description=attr_data['const']
            )
        if 'items' in attr_data:
            array = SpecObject(metaspec=self, kind=KIND_ARRAY)
            self._add_array_items(array, attr_data['items'])
            return array
        if 'type' not in attr_data:
            raise MetaspecError(
                f'The attribute "{key}" needs one of "type", "items" or "const".'
            )
        return self._get_object(attr_data['type'])

    def _add_array_items(self, array, item_slugs):
        # Item keys are positional. get_child_relationships() sorts by
        # them, so the declared order is preserved.
        for i, slug in enumerate(item_slugs):
            self._add_attribute(array, str(i), self._get_object(slug))

    def _add_attribute(self, parent, key, child, is_required=False, description='',
            extra_json_schema=None):
        attribute = Attribute(
            parent, key, child, is_required, description, extra_json_schema
        )
        parent.attributes.append(attribute)
        child.parent_attributes.append(attribute)
        return attribute

    def _get_object(self, slug):
        try:
            return self.objects[slug]
        except KeyError:
            raise MetaspecError(f'Unknown object "{slug}".')

    # -- Examples ---------------------------------------------------------

    def _build_examples(self, examples_data, media_dir):
        for format_data in examples_data.get('comparisonFormats', []):
            comparison_format = ComparisonFormat(format_data)
            self.comparison_formats[comparison_format.slug] = comparison_format

        for example_data in examples_data.get('examples', []):
            example = Example(self, example_data, media_dir)
            for comparison_data in example_data.get('comparisons', []):
                slug = comparison_data['format']
                try:
                    comparison_format = self.comparison_formats[slug]
                except KeyError:
                    raise MetaspecError(f'Unknown comparison format "{slug}".')
                example.comparisons.append(
                    Comparison(example, comparison_format, comparison_data, media_dir)
                )
            self.examples.append(example)

        self.examples_by_slug = {e.slug: e for e in self.examples}
        self._index_example_objects()

    def _index_example_objects(self):
        """
        Works out which objects each example uses, by reading the example
        documents. This replaces a cache table that had to be rebuilt
        whenever an example changed, and had fallen out of date.
        """
        self.examples_by_object = {}
        for example in self.examples:
            try:
                example.spec_objects = accumulate_used_objects(
                    json.loads(example.get_document_text()), self.root_object
                )
            except (ValueError, MetaspecError) as e:
                raise MetaspecError(f'Example "{example.slug}": {e}')
            for obj in example.spec_objects:
                if obj.has_docs_page():
                    self.examples_by_object.setdefault(obj, []).append(example)

    # -- Lookups ----------------------------------------------------------

    def documented_objects(self):
        return [o for o in self.objects.values() if o.has_docs_page()]

    def get_examples_for_object(self, obj):
        return sorted(
            self.examples_by_object.get(obj, []), key=lambda e: e.name.lower()
        )

    def get_comparisons(self, comparison_format):
        result = [
            c for e in self.examples for c in e.comparisons
            if c.doc_format is comparison_format
        ]
        result.sort(key=lambda c: c.position)
        return result

    def featured_examples(self):
        return sorted(
            (e for e in self.examples if e.is_featured), key=lambda e: e.name
        )

def accumulate_used_objects(json_data, object_def):
    """
    Given JSON data and the object describing it, returns the set of all
    objects used within, recursively.
    """
    result = set()
    if object_def.is_array() or object_def.is_user_defined_dict():
        child_defs = [a.child for a in object_def.get_child_relationships()]
        values = json_data.values() if isinstance(json_data, dict) else json_data
        for child_data in values:
            result.update(
                accumulate_used_objects(
                    child_data, get_object_for_data(child_data, child_defs)
                )
            )
    else:
        result.add(object_def)
        for attribute in object_def.get_child_relationships():
            if isinstance(json_data, dict) and attribute.child_key in json_data:
                result.update(
                    accumulate_used_objects(json_data[attribute.child_key], attribute.child)
                )
    return result

# -- Loading ---------------------------------------------------------------

def load_metaspec(source_dir=None, media_dir=None):
    """
    Reads the metaspec files from disk and returns a Metaspec.
    """
    source_dir = source_dir or settings.METASPEC_DIR
    media_dir = media_dir or settings.MEDIA_DIR
    with open(os.path.join(source_dir, METASPEC_FILENAME), 'r') as fp:
        data = json.load(fp, object_pairs_hook=reject_duplicate_keys)
    with open(os.path.join(source_dir, EXAMPLES_FILENAME), 'r') as fp:
        examples_data = json.load(fp, object_pairs_hook=reject_duplicate_keys)
    return Metaspec(data, examples_data, source_dir, media_dir)

def reject_duplicate_keys(pairs):
    """
    A json.load() hook that refuses duplicate keys. Python's default is
    to keep the last one, which would silently drop an attribute.
    """
    result = {}
    for key, value in pairs:
        if key in result:
            raise MetaspecError(f'Duplicate key "{key}".')
        result[key] = value
    return result

_cache = None

def get_metaspec():
    """
    Returns the Metaspec, reloading it if any source file has changed.

    The reload check means the local web server always reflects what's on
    disk, so the edit-and-refresh loop needs no restart.
    """
    global _cache
    fingerprint = source_fingerprint()
    if _cache is None or _cache[0] != fingerprint:
        _cache = (fingerprint, load_metaspec())
    return _cache[1]

def source_fingerprint():
    """
    Returns the modification times of every file the metaspec is built
    from, including the example documents and page content.
    """
    source_dir = settings.METASPEC_DIR
    paths = [
        os.path.join(source_dir, METASPEC_FILENAME),
        os.path.join(source_dir, EXAMPLES_FILENAME),
    ]
    for directory in (
        os.path.join(source_dir, CONTENT_DIRNAME),
        os.path.join(settings.MEDIA_DIR, 'examples'),
    ):
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames.sort()
            paths.extend(
                os.path.join(dirpath, f) for f in sorted(filenames)
                if not f.startswith('.')
            )
    return tuple((p, os.path.getmtime(p)) for p in paths if os.path.exists(p))

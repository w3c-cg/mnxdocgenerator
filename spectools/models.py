from django.contrib import admin
from django.db import models
from django.urls import reverse

FORMAT_TEXT = 1
FORMAT_HTML = 2
FORMAT_CHOICES = (
    (FORMAT_TEXT, 'Plain text'),
    (FORMAT_HTML, 'Raw HTML'),
)

class SiteOptions(models.Model):
    # Singleton model that's used to store general metadata
    # about the documentation website.
    site_name = models.CharField(max_length=100)
    xml_format_name = models.CharField(max_length=100)
    sidebar_html = models.TextField(blank=True,
        help_text='Raw HTML to put into the left sidebar of each page.'
    )

    class Meta:
        db_table = 'site_options'
        verbose_name_plural = 'site options'

    def __str__(self):
        return self.site_name

class XMLSchema(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True)
    is_json = models.BooleanField(default=False)
    version = models.CharField(max_length=12, blank=True)

    class Meta:
        db_table = 'xml_schemas'
        verbose_name = 'XML schema'
        verbose_name_plural = 'XML schemas'

    def __str__(self):
        return self.name

    def reference_url(self):
        return reverse('reference_homepage', args=(self.slug,))

    def data_types_url(self):
        return reverse('data_type_list', args=(self.slug,))

    def examples_url(self):
        return reverse('example_list', args=(self.slug,))

    def elements_url(self):
        return reverse('element_list', args=(self.slug,))

    def element_tree_url(self):
        return reverse('element_tree', args=(self.slug,))

    def json_objects_url(self):
        return reverse('json_object_list', args=(self.slug,))

class DocumentFormat(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'document_formats'

    def __str__(self):
        return self.name

    def comparison_url(self):
        return reverse('format_comparison_detail', args=(self.slug,))

class JSONObject(models.Model):
    OBJECT_TYPE_DICT = 1
    OBJECT_TYPE_ARRAY = 2
    OBJECT_TYPE_STRING = 3
    OBJECT_TYPE_NUMBER = 4
    OBJECT_TYPE_BOOLEAN = 5
    OBJECT_TYPE_LITERAL_STRING = 6
    OBJECT_TYPE_DICT_USER_DEFINED = 7
    OBJECT_TYPE_CHOICES = (
        (OBJECT_TYPE_DICT, 'Dictionary'),
        (OBJECT_TYPE_DICT_USER_DEFINED, 'Dictionary with user-defined keys'),
        (OBJECT_TYPE_ARRAY, 'Array'),
        (OBJECT_TYPE_STRING, 'String'),
        (OBJECT_TYPE_NUMBER, 'Number'),
        (OBJECT_TYPE_BOOLEAN, 'Boolean'),
        (OBJECT_TYPE_LITERAL_STRING, 'Literal string'),
    )
    ROOT_OBJECT_NAME = '__root__'
    GLOBAL_ATTRS_OBJECT_NAME = '__globalattrs__'

    name = models.CharField(max_length=80)
    slug = models.CharField(max_length=80)
    schema = models.ForeignKey(XMLSchema, on_delete=models.CASCADE, default=1)
    object_type = models.SmallIntegerField(choices=OBJECT_TYPE_CHOICES)
    uses_global_attrs = models.BooleanField(default=True)
    regex = models.CharField(max_length=255, blank=True,
        help_text="For strings, an optional regex to use for this value. Make sure to use ^ at the start and $ at the end.")

    # For OBJECT_TYPE_LITERAL_STRING, this contains the string.
    # For other object_types, this is a prose description displayed in the docs.
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'json_objects'
        verbose_name = 'JSON object'
        verbose_name_plural = 'JSON objects'
        unique_together = (
            ('schema', 'slug'),
        )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('json_object_detail', args=(self.schema.slug, self.slug))

    def has_docs_page(self):
        return self.object_type not in {JSONObject.OBJECT_TYPE_ARRAY, JSONObject.OBJECT_TYPE_LITERAL_STRING, JSONObject.OBJECT_TYPE_DICT_USER_DEFINED}

    def is_array(self):
        return self.object_type == JSONObject.OBJECT_TYPE_ARRAY

    def is_literal_string(self):
        return self.object_type == JSONObject.OBJECT_TYPE_LITERAL_STRING

    def is_user_defined_dict(self):
        return self.object_type == JSONObject.OBJECT_TYPE_DICT_USER_DEFINED

    def is_global_attrs_object(self):
        return self.name == JSONObject.GLOBAL_ATTRS_OBJECT_NAME

    def docs_page_title(self):
        if self.is_global_attrs_object():
            return 'Global attributes'
        else:
            return f'The {self.name} object'

    def get_child_relationships(self, include_global_attrs=False):
        result = list(JSONObjectRelationship.objects.filter(parent=self).order_by('child_key'))
        if include_global_attrs:
            global_attrs = self.get_global_child_relationships()
            if global_attrs:
                result += global_attrs
                result.sort(key=lambda x: x.child_key)
        return result

    def get_global_child_relationships(self):
        result = []
        if self.object_type == JSONObject.OBJECT_TYPE_DICT and self.uses_global_attrs:
            result = list(JSONObjectRelationship.objects.filter(parent__name=JSONObject.GLOBAL_ATTRS_OBJECT_NAME).order_by('child_key'))
        return result

    def get_parent_relationships(self):
        result = []
        for rel in JSONObjectRelationship.objects.filter(child=self).exclude(parent__name=JSONObject.GLOBAL_ATTRS_OBJECT_NAME).order_by('parent__name', 'child_key'):
            if rel.parent.has_docs_page():
                result.append(rel)
            else:
                parent_rel = JSONObjectRelationship.objects.filter(
                    child=rel.parent
                )[0]
                result.append(parent_rel)

        return result

    @admin.display(description='Object type', ordering='object_type')
    def pretty_object_type(self):
        return {
            JSONObject.OBJECT_TYPE_DICT: 'Dictionary',
            JSONObject.OBJECT_TYPE_DICT_USER_DEFINED: 'Dictionary with user-defined keys',
            JSONObject.OBJECT_TYPE_ARRAY: 'Array',
            JSONObject.OBJECT_TYPE_STRING: 'String',
            JSONObject.OBJECT_TYPE_NUMBER: 'Number',
            JSONObject.OBJECT_TYPE_BOOLEAN: 'Boolean',
            JSONObject.OBJECT_TYPE_LITERAL_STRING: 'Literal string',
        }[self.object_type]

    def matches_json(self, json_data):
        """
        Given a JSON object, returns True if the object appears to be
        described by this JSONObject definition.

        This only searches one level deep.
        """
        object_type = self.object_type
        if object_type == JSONObject.OBJECT_TYPE_DICT:
            child_rels = {r.child_key: r for r in self.get_child_relationships(include_global_attrs=True)}
            for k in json_data.keys():
                if k not in child_rels:
                    return False
            return True
        elif object_type == JSONObject.OBJECT_TYPE_DICT_USER_DEFINED:
            return isinstance(json_data, dict)
        elif object_type == JSONObject.OBJECT_TYPE_ARRAY:
            return isinstance(json_data, list)
        elif object_type in {JSONObject.OBJECT_TYPE_STRING, JSONObject.OBJECT_TYPE_LITERAL_STRING}:
            return isinstance(json_data, str)
        elif object_type == JSONObject.OBJECT_TYPE_NUMBER:
            return isinstance(json_data, (int, float))
        else:
            raise NotImplementedError()

    @staticmethod
    def get_jsonobject_for_data(json_data, object_def_list):
        """
        Given JSON data and a list of potential JSONObjects that describe it,
        returns the JSONObject that describes it.
        """
        if len(object_def_list) == 1:
            return object_def_list[0] # Common case.
        for object_def in object_def_list:
            if object_def.matches_json(json_data):
                return object_def

        # By now, one of the given object_def_list should have matched.
        # If not, raise an exception to bring attention to the wonky data.
        raise ValueError()

class JSONObjectRelationship(models.Model):
    parent = models.ForeignKey(JSONObject, on_delete=models.CASCADE, related_name='parent_rel')
    child_key = models.CharField(max_length=80)
    child = models.ForeignKey(JSONObject, on_delete=models.CASCADE, related_name='child_rel')
    is_required = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'json_object_relationships'
        verbose_name = 'JSON object relationship'
        verbose_name_plural = 'JSON object relationships'
        unique_together = (
            ('parent', 'child_key'),
        )

    def __repr__(self):
        return f'<JSONObjectRelationship parent="{self.parent.name}" child="{self.child.name}">'

class JSONObjectEnum(models.Model):
    parent = models.ForeignKey(JSONObject, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'json_object_enums'
        verbose_name = 'JSON object enum value'
        verbose_name_plural = 'JSON object enum values'
        unique_together = (
            ('parent', 'name'),
        )

    def __str__(self):
        return self.name

    def pretty_name(self):
        if self.parent.object_type == JSONObject.OBJECT_TYPE_STRING:
            return f'"{self.name}"'
        else:
            return self.name

class ExampleDocument(models.Model):
    name = models.CharField(max_length=300)
    slug = models.CharField(max_length=100)
    schema = models.ForeignKey(XMLSchema, on_delete=models.CASCADE, default=1)
    blurb = models.TextField(blank=True)
    document = models.TextField(blank=True)
    document_path = models.CharField(max_length=300, blank=True,
        help_text='Path to the document within the doctools/media directory, e.g., "examples/json/beams.json".')
    image_url = models.CharField(max_length=300, blank=True,
        help_text='Path to the image within the doctools/media directory, e.g., "/static/examples/test.jpg".'
    )
    is_featured = models.BooleanField(default=False)

    class Meta:
        db_table = 'example_documents'
        unique_together = (
            ('schema', 'slug'),
        )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from spectools.utils.datautils import update_example_elements
        update_example_elements(self)

    def get_absolute_url(self):
        return reverse('example_detail', args=(self.schema.slug, self.slug,))

    def get_document_text(self):
        if self.document:
            return self.document
        else:
            from django.conf import settings
            import os.path
            filename = os.path.join(settings.STATICFILES_DIRS[0], self.document_path)
            return open(filename, 'r').read()

class ExampleDocumentComparison(models.Model):
    example = models.ForeignKey(ExampleDocument, on_delete=models.CASCADE)
    doc_format = models.ForeignKey(DocumentFormat, on_delete=models.CASCADE)
    preamble = models.TextField(blank=True)
    document = models.TextField()
    position = models.SmallIntegerField()

    class Meta:
        db_table = 'example_comparisons'

    def get_absolute_url(self):
        return self.doc_format.comparison_url() + f'#{self.example.slug}'

    def preamble_html(self):
        if self.preamble:
            return '\n'.join(f'<p class="examplenotes">{line}</p>' for line in self.preamble.split('\n') if line)
        return ''

class ExampleDocumentObject(models.Model):
    # This is a cache of each JSONObject used in each
    # ExampleDocument. It's updated via ExampleDocument.save().
    example = models.ForeignKey(ExampleDocument, on_delete=models.CASCADE)
    json_object = models.ForeignKey(JSONObject, null=True, on_delete=models.CASCADE)

    class Meta:
        db_table = 'example_objects'

class StaticPageCollection(models.Model):
    title = models.CharField(max_length=255)
    url = models.CharField(max_length=150,
        help_text='Make sure it starts and ends with slashes.'
    )
    schema = models.ForeignKey(XMLSchema, null=True, blank=True, on_delete=models.SET_NULL)
    order = models.SmallIntegerField()

    class Meta:
        db_table = 'static_page_collections'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.url

class StaticPage(models.Model):
    title = models.CharField(max_length=255)
    url = models.CharField(max_length=150,
        help_text='Make sure it starts and ends with slashes.'
    )
    collection = models.ForeignKey(StaticPageCollection, on_delete=models.CASCADE)
    order = models.SmallIntegerField(help_text='This is the order of the page within the collection. Ordering is ascending.')
    content = models.TextField()

    class Meta:
        db_table = 'static_pages'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.url

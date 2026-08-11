from django import http
from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, render
from spectools.utils import htmlutils
from spectools.models import *

def homepage(request):
    return render(request, 'homepage.html', {
        'schemas': XMLSchema.objects.order_by('name'),
        'static_pages': StaticPage.objects.select_related('collection').order_by('collection__order', 'order'),
    })

def reference_homepage(request, schema_slug):
    schema = get_object_or_404(XMLSchema, slug=schema_slug)
    return render(request, 'reference_homepage.html', {
        'schema': schema,
        'featured_examples': ExampleDocument.objects.filter(schema=schema, is_featured=True).order_by('name'),
    })

def json_object_list(request, schema_slug):
    schema = get_object_or_404(XMLSchema, slug=schema_slug)
    objects = JSONObject.objects.select_related('schema').filter(
        schema=schema,
    ).exclude(
        Q(object_type=JSONObject.OBJECT_TYPE_ARRAY) | Q(object_type=JSONObject.OBJECT_TYPE_DICT_USER_DEFINED) | Q(object_type=JSONObject.OBJECT_TYPE_LITERAL_STRING)
    ).order_by('name')
    return render(request, 'json_object_list.html', {
        'schema': schema,
        'objects': objects,
    })

def json_object_detail(request, schema_slug, slug):
    json_object = get_object_or_404(
        JSONObject.objects.select_related('schema'),
        schema__slug=schema_slug,
        slug=slug
    )
    if not json_object.has_docs_page():
        raise http.Http404()
    return render(request, 'json_object_detail.html', {
        'object': json_object,
        'child_relationships': json_object.get_child_relationships(),
        'child_relationships_global': json_object.get_global_child_relationships(),
        'parent_relationships': json_object.get_parent_relationships(),
        'enum_values': JSONObjectEnum.objects.filter(parent=json_object).order_by('name'),
        'examples': ExampleDocumentObject.objects.filter(json_object=json_object).select_related('example').order_by(Lower('example__name')),
        'global_attrs_obj': JSONObject.objects.filter(name=JSONObject.GLOBAL_ATTRS_OBJECT_NAME)[0],
    })

def json_schema(request, schema_slug):
    from spectools.utils.jsonschema import make_json_schema
    import json
    schema_obj = make_json_schema(schema_slug)
    schema_str = json.dumps(schema_obj, indent=2, sort_keys=True)
    return http.HttpResponse(schema_str, content_type='text/plain')

def example_list(request, schema_slug):
    schema = get_object_or_404(XMLSchema, slug=schema_slug)
    return render(request, 'example_list.html', {
        'schema': schema,
        'examples': ExampleDocument.objects.filter(schema=schema).order_by(Lower('name')),
    })

def example_detail(request, schema_slug, slug):
    example = get_object_or_404(
        ExampleDocument.objects.select_related('schema'),
        schema__slug=schema_slug,
        slug=slug
    )
    return render(request, 'example_detail.html', {
        'example': example,
        'augmented_doc': htmlutils.get_augmented_example(request.path, example.schema, example.get_document_text(), diffs_use_divs=False)[1],
        'comparisons': ExampleDocumentComparison.objects.filter(example=example).select_related('doc_format'),
    })

def format_comparison_detail(request, slug):
    other_format = get_object_or_404(DocumentFormat, slug=slug)
    main_schema = XMLSchema.objects.get(id=1)
    comparisons = []
    for edc in ExampleDocumentComparison.objects.filter(doc_format=other_format).select_related('example').order_by('position'):
        highlight_diffs, doc_html = htmlutils.get_augmented_example(request.path, main_schema, edc.example.get_document_text(), True)
        comparisons.append({
            'example': edc.example,
            'preamble_html': edc.preamble_html(),
            'document_html': doc_html,
            'other_document_html': htmlutils.get_prettified_xml(edc.document),
            'highlight_diffs': highlight_diffs,
        })
    return render(request, 'format_comparison_detail.html', {
        'other_format': other_format,
        'comparisons': comparisons,
    })

def static_page_or_collection_detail(request):
    try:
        spc = StaticPageCollection.objects.filter(url=request.path)[0]
    except IndexError:
        pass
    else:
        return static_collection_detail(request, spc)
    sp = get_object_or_404(StaticPage, url=request.path)
    return render(request, 'static_page.html', {
        'static_page': sp,
    })

def static_collection_detail(request, collection):
    static_pages = StaticPage.objects.filter(collection=collection).order_by('order')
    return render(request, 'static_page_collection.html', {
        'collection': collection,
        'static_pages': static_pages,
    })

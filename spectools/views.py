from django import http
from django.shortcuts import render
from spectools.metaspec import get_metaspec
from spectools.utils import htmlutils

def get_format_or_404(metaspec, schema_slug):
    if schema_slug != metaspec.format.slug:
        raise http.Http404()
    return metaspec.format

def homepage(request):
    return render(request, 'homepage.html', {})

def reference_homepage(request, schema_slug):
    metaspec = get_metaspec()
    return render(request, 'reference_homepage.html', {
        'schema': get_format_or_404(metaspec, schema_slug),
        'featured_examples': metaspec.featured_examples(),
    })

def json_object_list(request, schema_slug):
    metaspec = get_metaspec()
    return render(request, 'json_object_list.html', {
        'schema': get_format_or_404(metaspec, schema_slug),
        'objects': sorted(metaspec.documented_objects(), key=lambda o: o.name),
    })

def json_object_detail(request, schema_slug, slug):
    metaspec = get_metaspec()
    get_format_or_404(metaspec, schema_slug)
    try:
        json_object = metaspec.objects[slug]
    except KeyError:
        raise http.Http404()
    if not json_object.has_docs_page():
        raise http.Http404()
    return render(request, 'json_object_detail.html', {
        'object': json_object,
        'child_relationships': json_object.get_child_relationships(),
        'child_relationships_global': json_object.get_global_child_relationships(),
        'parent_relationships': json_object.get_parent_relationships(),
        'enum_values': sorted(json_object.enum_values, key=lambda e: e.name),
        'examples': metaspec.get_examples_for_object(json_object),
        'global_attrs_obj': metaspec.global_attrs_object,
    })

def json_schema(request, schema_slug):
    from spectools.utils.jsonschema import make_json_schema
    import json
    schema_obj = make_json_schema(schema_slug)
    schema_str = json.dumps(schema_obj, indent=2, sort_keys=True)
    return http.HttpResponse(schema_str, content_type='text/plain')

def example_list(request, schema_slug):
    metaspec = get_metaspec()
    return render(request, 'example_list.html', {
        'schema': get_format_or_404(metaspec, schema_slug),
        'examples': sorted(metaspec.examples, key=lambda e: e.name.lower()),
    })

def example_detail(request, schema_slug, slug):
    metaspec = get_metaspec()
    get_format_or_404(metaspec, schema_slug)
    try:
        example = metaspec.examples_by_slug[slug]
    except KeyError:
        raise http.Http404()
    return render(request, 'example_detail.html', {
        'example': example,
        'augmented_doc': htmlutils.get_augmented_example(request.path, metaspec.root_object, example.get_document_text(), diffs_use_divs=False)[1],
        'comparisons': example.comparisons,
    })

def format_comparison_detail(request, slug):
    metaspec = get_metaspec()
    try:
        other_format = metaspec.comparison_formats[slug]
    except KeyError:
        raise http.Http404()
    comparisons = []
    for comparison in metaspec.get_comparisons(other_format):
        highlight_diffs, doc_html = htmlutils.get_augmented_example(
            request.path, metaspec.root_object, comparison.example.get_document_text(), True
        )
        comparisons.append({
            'example': comparison.example,
            'preamble_html': comparison.preamble_html(),
            'document_html': doc_html,
            'other_document_html': htmlutils.get_prettified_xml(comparison.get_document_text()),
            'highlight_diffs': highlight_diffs,
        })
    return render(request, 'format_comparison_detail.html', {
        'other_format': other_format,
        'comparisons': comparisons,
    })

def static_page_or_collection_detail(request):
    metaspec = get_metaspec()
    for collection in metaspec.page_collections:
        if collection.url == request.path:
            return static_collection_detail(request, collection)
    for page in metaspec.pages:
        if page.url == request.path:
            return render(request, 'static_page.html', {
                'static_page': page,
            })
    raise http.Http404()

def static_collection_detail(request, collection):
    return render(request, 'static_page_collection.html', {
        'collection': collection,
        'static_pages': collection.pages,
    })

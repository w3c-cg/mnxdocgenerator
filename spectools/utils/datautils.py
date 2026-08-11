from spectools.models import JSONObject, ExampleDocumentObject
import json

def update_example_elements(example):
    """
    Given an ExampleDocument, creates all necessary
    ExampleDocumentObject objects.

    Any existing ExampleDocumentObject objects are
    untouched -- except if they're no longer represented
    in the given ExampleDocument (in which case they're
    deleted).
    """
    update_example_elements_json(example)

def accumulate_used_json_objects(json_data, object_def):
    """
    Given JSON data and a JSONObject that describes what level of the
    document tree we're in, returns a set of all JSONObjects used
    within (recursively).
    """
    result = set()
    if object_def.is_array() or object_def.is_user_defined_dict():
        child_object_defs = [c.child for c in object_def.get_child_relationships()]
        for child_obj in json_data:
            child_object_def = JSONObject.get_jsonobject_for_data(child_obj, child_object_defs)
            result.update(accumulate_used_json_objects(child_obj, child_object_def))
    else:
        result.add(object_def)
        for rel in object_def.get_child_relationships():
            if rel.child_key in json_data:
                result.update(accumulate_used_json_objects(json_data[rel.child_key], rel.child))
    return result

def update_example_elements_json(example):
    schema = example.schema
    root_object = JSONObject.objects.get(schema=schema, name=JSONObject.ROOT_OBJECT_NAME)
    example_doc = json.loads(example.get_document_text())
    seen_objects = accumulate_used_json_objects(example_doc, root_object)
    for existing in ExampleDocumentObject.objects.filter(example=example):
        if existing.json_object in seen_objects:
            seen_objects.remove(existing.json_object)
        else:
            existing.delete()
    for obj in seen_objects:
        ExampleDocumentObject.objects.create(
            example=example,
            json_object=obj,
        )

from spectools.models import JSONObject
from spectools.utils.relative_url import get_relative_url
import xml.sax
import json

INDENT_SIZE = 3
DIFF_ELEMENT = 'metadiff'
PRESERVE_SPACE_ATTRIBUTE = 'preserve-space'

class DiffElementContentHandler(xml.sax.handler.ContentHandler):
    def __init__(self, diffs_use_divs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diffs_use_divs = diffs_use_divs
        self.result = []
        self.pending_diff_class = None
        self.saw_diff = False

    def handle_start_diff_element(self):
        self.pending_diff_class = 'diff'
        self.saw_diff = True

    def handle_end_diff_element(self):
        self.pending_diff_class = 'nodiff'

    def get_pending_diff_markup(self):
        if self.pending_diff_class:
            if self.diffs_use_divs:
                result = f'</div><div class="xmlmarkup {self.pending_diff_class}">'
            else:
                result = f'</span><span class="{self.pending_diff_class}">'
            self.pending_diff_class = None
        else:
            result = ''
        return result

    def get_result(self):
        html = '\n'.join(self.result)
        extraclass = ' nodiff' if self.saw_diff else ''
        if self.diffs_use_divs:
            return f'<div class="xmlmarkup{extraclass}">{html}</div>'
        else:
            return f'<div class="xmlmarkup"><span class="{extraclass}">{html}</span></div>'

def get_augmented_example(current_url, schema, raw_document, diffs_use_divs=True):
    return get_augmented_example_json(current_url, schema, raw_document, diffs_use_divs)

def get_augmented_example_json(current_url, schema, raw_document, diffs_use_divs=True):
    saw_diff = False # TODO: Implement this.
    result = get_augmented_example_json_inner(
        current_url,
        json.loads(raw_document),
        JSONObject.objects.get(schema=schema, name=JSONObject.ROOT_OBJECT_NAME),
        indent_level=0
    )
    output_html = []
    collapse_next = False
    for indent_level, text, collapse, highlight in result:
        if highlight:
            text = f'<b class="markuphl">{text}</b>'
        if collapse_next and output_html:
            output_html[-1] += ' ' + text
        else:
            output_html.append((' ' * INDENT_SIZE * indent_level) + str(text))
        collapse_next = collapse
    return (saw_diff, '<div class="xmlmarkup">' + '\n'.join(output_html) + '</div>')

def json_key_sorter(x):
    """
    A sorting function (suitable for passing as the 'key' argument
    to sorted()) that always puts the values "id", "mnx" and "type" first,
    in that order.

    We use this because it helps make the docs clearer if these keys
    are listed first within a given object.
    """
    return (x != 'id', x != 'mnx', x != 'type', x)

def get_augmented_example_json_inner(current_url, json_data, object_def=None, indent_level=0, add_comma=False, highlight=False):
    result = []
    if object_def is None:
        result.append([
            indent_level,
            f'<span class="tag">{json.dumps(json_data, ensure_ascii=False)}</span>',
            False,
            highlight
        ])
    elif isinstance(json_data, (dict, list)) and not json_data:
        # Special case: For empty dicts or empty lists, use "{}" and "[]"
        # rather than splitting the opening/closing symbols over two lines.
        result.append([
            indent_level,
            json.dumps(json_data, ensure_ascii=False),
            False,
            highlight
        ])
    elif isinstance(json_data, dict):
        child_rels = {r.child_key: r for r in object_def.get_child_relationships(include_global_attrs=True)}
        result.append([
            indent_level,
            '{',
            False,
            highlight
        ])
        vendor_data = json_data.pop('_x', {})
        highlighted_keys = vendor_data.get('mnxdocs', {}).get('highlight', [])
        keys = list(sorted(json_data.keys(), key=json_key_sorter))
        for i, key in enumerate(keys):
            value = f'"{key}"'
            if object_def.has_docs_page():
                value = f'<a class="tag" href="{get_relative_url(current_url, object_def.get_absolute_url())}">{value}</a>'
            result.append([
                indent_level + 1,
                f'{value}:',
                True,
                highlight or key in highlighted_keys
            ])
            if object_def.is_user_defined_dict():
                child_rel = list(child_rels.values())[0].child
            else:
                child_rel = child_rels[key].child if key in child_rels else None
            result.extend(get_augmented_example_json_inner(
                current_url,
                json_data[key],
                child_rel,
                indent_level + 1,
                add_comma=i != len(keys) - 1,
                highlight=highlight or key in highlighted_keys
            ))
        result.append([
            indent_level,
            '}',
            False,
            highlight
        ])
    elif isinstance(json_data, list):
        child_object_defs = [c.child for c in object_def.get_child_relationships(include_global_attrs=True)]
        result.append([
            indent_level,
            '[',
            False,
            highlight
        ])
        for i, child_obj in enumerate(json_data):
            child_object_def = JSONObject.get_jsonobject_for_data(child_obj, child_object_defs)
            result.extend(get_augmented_example_json_inner(
                current_url,
                child_obj,
                child_object_def,
                indent_level + 1,
                add_comma=i != len(json_data) - 1,
                highlight=highlight
            ))
        result.append([
            indent_level,
            ']',
            False,
            highlight
        ])
    else:
        value = json.dumps(json_data, ensure_ascii=False)
        if object_def.has_docs_page():
            value = f'<a class="tag" href="{get_relative_url(current_url, object_def.get_absolute_url())}">{value}</a>'
        result.append([
            indent_level,
            value,
            False,
            highlight
        ])
    if add_comma:
        result[-1][1] += ','
    return result

class XMLPrettifier(DiffElementContentHandler):
    def __init__(self, diffs_use_divs, *args, **kwargs):
        super().__init__(diffs_use_divs, *args, **kwargs)
        self.indent_level = 0
        self.last_tag_opened = None

    def startElement(self, name, attrs):
        if name == DIFF_ELEMENT:
            self.handle_start_diff_element()
            return
        html = [
            self.get_pending_diff_markup(),
            ' ' * self.indent_level * INDENT_SIZE,
            f'&lt;<span class="tag">{name}</span>'
        ]
        if attrs:
            html.extend(f' <span class="attrname">{k}</span>="<span class="attrval">{v}</span>"' for (k, v) in attrs.items())
        html.append('&gt;')
        self.result.append(''.join(html))
        self.indent_level += 1
        self.last_tag_opened = name

    def characters(self, content):
        if content and content.strip():
            self.result.append((' ' * self.indent_level * INDENT_SIZE) + content.strip())

    def endElement(self, name):
        if name == DIFF_ELEMENT:
            self.handle_end_diff_element()
            return
        self.indent_level -= 1
        result = self.result
        if name == self.last_tag_opened:
            previous_line = result[-1].strip()
            if previous_line.startswith('&lt;'):
                result[-1] += f'&lt;/<span class="tag">{name}</span>&gt;'
            else:
                result[-2] += previous_line + f'&lt;/<span class="tag">{name}</span>&gt;'
                del result[-1]
        else:
            html = [
                self.get_pending_diff_markup(),
                ' ' * self.indent_level * INDENT_SIZE,
                f'&lt;<span class="tag">/{name}</span>&gt;'
            ]
            result.append(''.join(html))

def get_prettified_xml(xml_string):
    reader = xml.sax.make_parser()
    handler = XMLPrettifier(diffs_use_divs=True)
    xml.sax.parseString(xml_string, handler)
    return handler.get_result()

from django.contrib import admin
from spectools.models import *

class SiteOptionsAdmin(admin.ModelAdmin):
    model = SiteOptions

class XMLSchemaAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}

class JSONChildElementsInline(admin.TabularInline):
    model = JSONObjectRelationship
    extra = 0
    fk_name = 'parent'

class JSONEnumsInline(admin.TabularInline):
    model = JSONObjectEnum
    extra = 0
    fk_name = 'parent'

class JSONObjectAdmin(admin.ModelAdmin):
    inlines = [JSONChildElementsInline, JSONEnumsInline]
    list_display = ['name', 'slug', 'pretty_object_type']
    list_filter = ['object_type']
    ordering = ['name']
    search_fields = ['name', 'slug']

class DocumentFormatAdmin(admin.ModelAdmin):
    model = DocumentFormat
    list_display = ['name', 'slug']

class ExampleDocumentComparisonInline(admin.TabularInline):
    model = ExampleDocumentComparison
    extra = 0

class ExampleDocumentAdmin(admin.ModelAdmin):
    inlines = [ExampleDocumentComparisonInline]
    list_display = ['name', 'slug', 'image_url', 'is_featured']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}

class StaticPageCollectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'url', 'schema', 'order']

class StaticPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'url', 'collection', 'order']

admin.site.register(SiteOptions, SiteOptionsAdmin)
admin.site.register(XMLSchema, XMLSchemaAdmin)
admin.site.register(JSONObject, JSONObjectAdmin)
admin.site.register(DocumentFormat, DocumentFormatAdmin)
admin.site.register(ExampleDocument, ExampleDocumentAdmin)
admin.site.register(StaticPageCollection, StaticPageCollectionAdmin)
admin.site.register(StaticPage, StaticPageAdmin)

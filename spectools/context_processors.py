from spectools.metaspec import get_metaspec

def docs_global_variables(request):
    return {
        'SITE_OPTIONS': get_metaspec().site,
    }

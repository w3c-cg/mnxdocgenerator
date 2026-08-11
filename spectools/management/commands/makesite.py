from django.conf import settings
from django.core.management.base import BaseCommand
from django.test.client import Client
from django.urls import reverse
from spectools.metaspec import get_metaspec
import os
import shutil

INDEX_FILE = 'index.html'

class SiteGenerator:
    def __init__(self, dirname:str, verbose=True):
        self.dirname = dirname
        self.verbose = verbose
        self.client = Client()
        self.metaspec = get_metaspec()
        if not os.path.exists(dirname):
            os.mkdir(dirname)

    def log(self, message):
        if self.verbose:
            print(message)

    def generate(self):
        metaspec = self.metaspec
        self.copy_media_files()
        self.generate_view('homepage')

        for comparison_format in metaspec.comparison_formats.values():
            self.generate_url(comparison_format.comparison_url())

        doc_format = metaspec.format
        self.generate_url(doc_format.reference_url())
        self.generate_url(doc_format.json_objects_url())
        self.generate_view('json_schema', doc_format.slug)
        self.generate_url(doc_format.examples_url())
        for example in metaspec.examples:
            self.generate_url(example.get_absolute_url())

        for obj in metaspec.documented_objects():
            self.generate_url(obj.get_absolute_url())

        for collection in metaspec.page_collections:
            self.generate_url(collection.url)
            for page in collection.pages:
                self.generate_url(page.url)

    def generate_view(self, view_name, *view_args):
        url = reverse(view_name, args=view_args)
        self.generate_url(url)

    def generate_url(self, url):
        html = self.client.get(url).content.decode('utf-8')

        # Normalize Windows newlines ("\r\n") to Unix style ("\n").
        html = html.replace('\r', '')

        file_dir = os.path.join(self.dirname, url[1:])
        self.log(file_dir)
        if url.endswith('/'):
            os.makedirs(file_dir, exist_ok=True)
            with open(os.path.join(file_dir, INDEX_FILE), 'w') as fp:
                fp.write(html)
        else:
            with open(file_dir, 'w') as fp:
                fp.write(html)

    def copy_media_files(self):
        self.log('Media files')
        output_dir = os.path.join(self.dirname, settings.STATIC_URL[1:])
        for static_dir in settings.STATICFILES_DIRS:
            shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)

class Command(BaseCommand):
    help = 'Generates the static site.'

    def add_arguments(self, parser):
        parser.add_argument('directory', nargs=1)

    def handle(self, **options):
        generator = SiteGenerator(options['directory'][0])
        generator.generate()

# MNX documentation generator

This is a Django app used to generate the documentation for
[MNX](https://w3c-cg.github.io/mnx/docs/), the music notation format.

The specification itself isn't here. It lives in the
[mnx repository](https://github.com/w3c-cg/mnx), in a pair of JSON files
under `doctools/`. This app reads those files and turns them into a website.

This tool consists of the following:

* A loader that reads the specification files into an object graph
(`spectools/metaspec.py`).

* A Django website that lets you view the documentation.

* Tools to generate a static version of the web documentation, and to
generate a JSON Schema from the specification.

* Commands to validate the specification files, and to validate the example
documents against the generated JSON Schema.

There's no database. See `doctools/README.md` and
`doctools/METASPEC-FORMAT.md` in the mnx repository for how to set this up
and how the specification files are structured.

# MNX and MusicXML documentation generator

This is a Django app used to generate the documentation
for the following W3C music notation formats:

* [MNX](https://w3c.github.io/mnx/docs/)
* [MusicXML](https://w3c.github.io/musicxml/)

It consists of the following:

* Database tables that can model XML and JSON data formats.

* A Django admin site that lets you edit the data formats
(both their technical semantics and human-readable documentation).

* A Django website that lets you view the documentation.

* Tools to generate static versions of the web documentation.

* Tools to serialize/deserialize the documentation data itself,
using an internal JSON format. This lets us put the documentation
data in source control as a JSON file instead of a binary
SQLite file.

# Semantic Sugar

**Project RDF graphs onto Pydantic models and back.**

`semantic-sugar` lets you define Pydantic models that map directly to RDF nodes, then project live graphs into validated, nested Python objects — or serialize them back to RDF.

## Installation

```bash
pip install semantic-sugar
```

## Quick example

```python
from rdflib import FOAF, Namespace
from semantic_sugar import RDFModel, Prop, Id, OfType

EX = Namespace("http://example.org/")


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    emails: list[str] = Prop(FOAF.mbox)


people = Person.project(graph)  # list[Person]
```

## How it works

Every projection passes through four independent stages:

| # | Stage | Question | Mechanism |
|---|---|---|---|
| 1 | **Selection** | Which RDF nodes are processed? | `select=` class keyword |
| 2 | **Derivation** | Which values come from each node? | `Prop(...)` field expressions |
| 3 | **Projection** | How are values assembled into objects? | Type annotations + projector |
| 4 | **Validation** | Does the object satisfy the consumer? | Plain Pydantic validators |

## Getting started

- **[Quickstart](quickstart.md)** — Define your first model using the built-in DCAT ontology.
- **[Field derivation](details/fields.md)** — Map model fields to RDF predicates, paths, and SPARQL queries.
- **[Projection](details/projection.md)** — Graph-driven and query-driven projection modes.
- **[Selectors](details/selectors.md)** — Control which RDF nodes are projected.
- **[Serialization](details/serialization.md)** — Convert model instances back to RDF graphs.
- **[Built-in ontologies](ontologies.md)** — Pre-defined models for existing ontologies.
- **[Errors](details/errors.md)** — Error handling and validation.

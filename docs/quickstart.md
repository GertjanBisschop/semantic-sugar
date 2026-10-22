# Quickstart

This guide walks you through defining your first `RDFModel` using the built-in DCAT ontology models.

## Defining a DCAT DataService

The library ships with pre-defined models for the [DCAT](https://www.w3.org/ns/dcat) vocabulary. Let's look at the `DataService` class:

```python
from rdflib import DCTERMS, Namespace, URIRef

from semantic_sugar import Id, OfType, Prop, RDFModel
from semantic_sugar.ontologies.dcat import DCAT


class DataService(RDFModel, select=OfType(DCAT.DataService)):
    """A data service that provides access to datasets."""

    uri: Id
    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    endpoint_url: URIRef | None = Prop(
        DCAT.endpointURL, on_many="error", default=None
    )
    endpoint_description: URIRef | None = Prop(
        DCAT.endpointDescription, on_many="first", default=None
    )
    conforms_to: URIRef | None = Prop(
        DCTERMS.conformsTo, on_many="first", default=None
    )
```

### What's happening here?

1. **`RDFModel`** — The base class. It extends Pydantic's `BaseModel` and adds RDF projection capabilities.

2. **`select=OfType(DCAT.DataService)`** — A selector that tells the projector to find all RDF nodes typed as `dcat:DataService` in the graph.

3. **`uri: Id`** — The `Id` marker designates this field to receive the RDF node's own IRI (or blank node identifier).

4. **`Prop(...)`** — Each `Prop` maps a model field to an RDF predicate. Options like `on_many="first"` control how multiple values are handled.

5. **Type annotations** — Cardinality is declared once:
   - `str | None` — zero or one value (optional)
   - `str` — exactly one value (required)
   - `list[str]` — zero or more values

## Projecting from a graph

```python
from rdflib import Graph
from semantic_sugar.ontologies.dcat import DataService

graph = Graph().parse("data.ttl", format="turtle")
services = DataService.project(graph)

for service in services:
    print(f"{service.title}: {service.endpoint_url}")
```

## Nested models

DCAT models nest naturally. A `Catalog` contains `Dataset` instances, which in turn contain `Distribution` instances that reference `DataService`:

```python
from semantic_sugar.ontologies.dcat import Catalog

catalogs = Catalog.project(graph)

for catalog in catalogs:
    print(catalog.title)
    for dataset in catalog.datasets:
        print(f"  - {dataset.title}")
        for dist in dataset.distributions:
            if dist.access_service:
                print(f"    via {dist.access_service.endpoint_url}")
```

## Serializing back to RDF

```python
from rdflib import Namespace, URIRef

EX = Namespace("https://example.com/")

service = DataService(
    uri=EX["my-service"],
    title="My WFS Service",
    description="A Web Feature Service",
    endpoint_url=URIRef("https://example.org/wfs"),
    conforms_to=URIRef("https://www.ogc.org/standards/wfs/"),
)

graph = service.to_rdf()
print(graph.serialize(format="turtle"))
```

## What's next?

- Learn about **[Selectors](details/selectors.md)** to control which nodes are projected.
- Explore **[Field derivation](details/fields.md)** for advanced `Prop` expressions.
- Read about **[Projection modes](details/projection.md)** — graph-driven vs query-driven.

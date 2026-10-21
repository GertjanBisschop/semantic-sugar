# Serialization

Convert `RDFModel` instances back to RDF graphs using `to_rdf()` and `to_rdf_many()`.

## to_rdf

Convert a single model instance to an RDF graph:

```python
from rdflib import Namespace, URIRef
from semantic_sugar.ontologies.dcat import DataService

EX = Namespace("https://example.com/")

service = DataService(
    uri=EX["my-service"],
    title="My WFS Service",
    description="A Web Feature Service for bathymetry data",
    endpoint_url=URIRef("https://ows.example.org/wfs"),
    conforms_to=URIRef("https://www.ogc.org/standards/wfs/"),
)

graph = service.to_rdf()
print(graph.serialize(format="turtle"))
```

Output:

```turtle
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://example.com/my-service> a dcat:DataService ;
    dcat:conformsTo <https://www.ogc.org/standards/wfs/> ;
    dcat:endpointURL <https://ows.example.org/wfs> ;
    dcterms:description "A Web Feature Service for bathymetry data" ;
    dcterms:title "My WFS Service" .
```

### How it works

The serializer inspects the model's field plan to determine predicates and values:

- The `Id` field becomes the subject node.
- The `select=` selector's `OfType` classes become `rdf:type` triples.
- Each `Prop` with a simple `URIRef` predicate becomes a triple.
- Nested `RDFModel` instances are recursively serialized.
- Fields with `Sparql` or callable sources are skipped (no stable predicate to reverse).

### Adding to an existing graph

```python
from rdflib import Graph

graph = Graph()
# ... add other triples ...
service.to_rdf(graph)  # adds triples to the existing graph
```

## to_rdf_many

Serialize multiple instances at once:

```python
from semantic_sugar import to_rdf_many

graph = to_rdf_many([service1, service2, service3])
```

## Nested models

Nested models are serialized with their own subject-predicate-object structure:

```python
from semantic_sugar.ontologies.dcat import Dataset, Distribution

dataset = Dataset(
    uri=EX["my-dataset"],
    title="Bathymetry Data",
    distributions=(
        Distribution(
            uri=EX["wfs-dist"],
            title="WFS Distribution",
            access_service=service,
        ),
    ),
)

graph = dataset.to_rdf()
```

The `dcat:distribution` predicate links the dataset to its distribution, and the distribution's `dcat:accessService` links to the service — all recursively.

## Limitations

- Fields derived from `Sparql` expressions or callables cannot be serialized back, as they have no stable predicate IRI.
- Path expressions (e.g., `EX.a / EX.b`) are not reversed.
- The serializer produces a minimal graph — it does not add inferred or derived triples.

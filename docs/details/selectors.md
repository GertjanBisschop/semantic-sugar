# Selectors

Selectors determine which RDF nodes are projected into model instances. They are set via the `select=` class keyword on an `RDFModel` and can be overridden per call.

## OfType

Selects nodes by their `rdf:type`. This is the most common selector.

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import OfType, RDFModel, Prop, Id


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" .
""",
    format="turtle",
)

people = Person.project(graph)
print(f"Found {len(people)} person(s)")
```

With `infer=True`, the selector also follows `rdfs:subClassOf` transitivity to include subtypes (expensive on large graphs):

```python exec="on" source="above"
from rdflib import Graph, FOAF, RDF, RDFS
from semantic_sugar import OfType, RDFModel, Prop, Id

# Define a Student subclass of Person
graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .

ex:Student rdfs:subClassOf foaf:Person .
<http://example.org/bob> a ex:Student ; foaf:name "Bob" .
""",
    format="turtle",
)


class Person(RDFModel, select=OfType(FOAF.Person, infer=True)):
    iri: Id
    name: str = Prop(FOAF.name)


people = Person.project(graph)
print(f"Found {len(people)} person(s) (including subtypes)")
```

Multiple types are accepted — a node matching any of them is selected:

```python exec="on" source="above"
from rdflib import Graph, DCAT
from semantic_sugar import OfType, RDFModel, Prop, Id


class Resource(RDFModel, select=OfType(DCAT.Dataset, DCAT.DataService)):
    iri: Id


graph = Graph().parse(
    data="""
@prefix dcat: <http://www.w3.org/ns/dcat#> .
<http://example.org/ds1> a dcat:Dataset .
<http://example.org/svc1> a dcat:DataService .
""",
    format="turtle",
)

resources = Resource.project(graph)
print(f"Found {len(resources)} resource(s)")
```

## Sparql

Use an arbitrary SPARQL SELECT query to select nodes. The query must bind `?this` to each selected node.

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import RDFModel, Sparql, Prop, Id


class ActivePerson(
    RDFModel,
    select=Sparql(
        "SELECT ?this WHERE { ?this a <http://xmlns.com/foaf/0.1/Person> . "
        "?this <http://example.org/active> true }"
    ),
):
    iri: Id
    name: str = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ex: <http://example.org/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" ; ex:active true .
<http://example.org/bob> a foaf:Person ; foaf:name "Bob" ; ex:active false .
""",
    format="turtle",
)

people = ActivePerson.project(graph)
print(f"Found {len(people)} active person(s)")
```

Prefixes already bound on the graph are available without explicit declaration.

## Nodes

Select an explicit list of nodes:

```python exec="on" source="above"
from rdflib import Graph, FOAF, URIRef
from semantic_sugar import Nodes, RDFModel, Prop, Id


class Person(
    RDFModel,
    select=Nodes(
        "http://example.org/alice",
        URIRef("http://example.org/bob"),
    ),
):
    iri: Id
    name: str = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" .
<http://example.org/bob> a foaf:Person ; foaf:name "Bob" .
<http://example.org/charlie> a foaf:Person ; foaf:name "Charlie" .
""",
    format="turtle",
)

people = Person.project(graph)
print(f"Found {len(people)} person(s) (only alice and bob)")
```

String arguments are automatically converted to `URIRef`.

## FromCallable

Wrap a callable that receives the graph and yields nodes:

```python exec="on" source="above"
from rdflib import Graph, FOAF, Namespace
from semantic_sugar import FromCallable, RDFModel, Prop, Id

EX = Namespace("http://example.org/")


def my_selector(graph: Graph):
    for s, _, _ in graph.triples((None, EX.active, None)):
        yield s


class Person(RDFModel, select=FromCallable(my_selector)):
    iri: Id
    name: str = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ex: <http://example.org/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" ; ex:active true .
<http://example.org/bob> a foaf:Person ; foaf:name "Bob" .
""",
    format="turtle",
)

people = Person.project(graph)
print(f"Found {len(people)} person(s) via callable selector")
```

## Combining selectors

Selectors support intersection (`&`) and union (`|`):

```python exec="on" source="above"
from rdflib import Graph, FOAF, DCAT, Namespace
from semantic_sugar import AllOf, AnyOf, OfType, Sparql, RDFModel, Prop, Id

EX = Namespace("http://example.org/")


# Intersection — nodes matching both selectors
class ActivePerson(
    RDFModel,
    select=OfType(FOAF.Person)
    & Sparql("SELECT ?this WHERE { ?this ex:active true }"),
):
    iri: Id
    name: str = Prop(FOAF.name)


# Union — nodes matching either selector
class AnyResource(
    RDFModel, select=OfType(DCAT.Dataset) | OfType(DCAT.Distribution)
):
    iri: Id


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix ex: <http://example.org/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" ; ex:active true .
<http://example.org/bob> a foaf:Person ; foaf:name "Bob" ; ex:active false .
<http://example.org/ds1> a dcat:Dataset .
<http://example.org/dist1> a dcat:Distribution .
""",
    format="turtle",
)

print(f"Active people: {len(ActivePerson.project(graph))}")
print(f"Any resources: {len(AnyResource.project(graph))}")
```

Equivalent constructors are `AllOf(*selectors)` and `AnyOf(*selectors)`.

## Per-call override

The class-level selector can be overridden at call time:

```python exec="on" source="above"
from rdflib import Graph, FOAF, Namespace
from semantic_sugar import OfType, Nodes, Sparql, RDFModel, Prop, Id

EX = Namespace("http://example.org/")


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ex: <http://example.org/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" ; ex:active true .
<http://example.org/bob> a foaf:Person ; foaf:name "Bob" ; ex:active false .
<http://example.org/charlie> a foaf:Person ; foaf:name "Charlie" ; ex:active true .
""",
    format="turtle",
)

# Use the class-level selector (OfType)
all_people = Person.project(graph)
print(f"All people: {len(all_people)}")

# Override with a specific node list
some_people = Person.project(graph, select=Nodes(EX.alice, EX.bob))
print(f"Some people: {len(some_people)}")

# Override with a custom SPARQL query
active_people = Person.project(
    graph, select=Sparql("SELECT ?this WHERE { ?this ex:active true }")
)
print(f"Active people: {len(active_people)}")
```

## Inheritance

Subclasses inherit the parent's selector unless they define their own:

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import OfType, RDFModel, Prop, Id


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)


class Student(Person):  # inherits OfType(FOAF.Person)
    iri: Id
    name: str = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" .
""",
    format="turtle",
)

# Student inherits the selector from Person
students = Student.project(graph)
print(f"Students (inherited selector): {len(students)}")
```

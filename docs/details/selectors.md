# Selectors

Selectors determine which RDF nodes are projected into model instances. They are set via the `select=` class keyword on an `RDFModel` and can be overridden per call.

## OfType

Selects nodes by their `rdf:type`. This is the most common selector.

```python
from rdflib import FOAF
from semantic_sugar import OfType, RDFModel

class Person(RDFModel, select=OfType(FOAF.Person)):
    ...
```

With `infer=True`, the selector also follows `rdfs:subClassOf` transitivity to include subtypes (expensive on large graphs):

```python
class Person(RDFModel, select=OfType(FOAF.Person, infer=True)):
    ...
```

Multiple types are accepted — a node matching any of them is selected:

```python
from rdflib import DCAT

class Resource(RDFModel, select=OfType(DCAT.Dataset, DCAT.DataService)):
    ...
```

## Sparql

Use an arbitrary SPARQL SELECT query to select nodes. The query must bind `?this` to each selected node.

```python
from semantic_sugar import RDFModel, Sparql

class ActivePerson(RDFModel, select=Sparql(
    "SELECT ?this WHERE { ?this a <http://xmlns.com/foaf/0.1/Person> . "
    "?this <http://example.org/active> true }"
)):
    ...
```

Prefixes already bound on the graph are available without explicit declaration.

## Nodes

Select an explicit list of nodes:

```python
from rdflib import URIRef
from semantic_sugar import Nodes, RDFModel

class Person(RDFModel, select=Nodes(
    "http://example.org/alice",
    URIRef("http://example.org/bob"),
)):
    ...
```

String arguments are automatically converted to `URIRef`.

## FromCallable

Wrap a callable that receives the graph and yields nodes:

```python
from rdflib import Graph
from semantic_sugar import FromCallable, RDFModel

def my_selector(graph: Graph):
    for s, _, _ in graph.triples((None, my_predicate, None)):
        yield s

class Person(RDFModel, select=FromCallable(my_selector)):
    ...
```

## Combining selectors

Selectors support intersection (`&`) and union (`|`):

```python
from semantic_sugar import AllOf, AnyOf, OfType, Sparql

# Intersection — nodes matching both selectors
class ActivePerson(RDFModel, select=OfType(FOAF.Person) & Sparql("SELECT ?this WHERE { ?this ex:active true }")):
    ...

# Union — nodes matching either selector
class AnyResource(RDFModel, select=OfType(DCAT.Dataset) | OfType(DCAT.Distribution)):
    ...
```

Equivalent constructors are `AllOf(*selectors)` and `AnyOf(*selectors)`.

## Per-call override

The class-level selector can be overridden at call time:

```python
# Use the class-level selector (OfType)
all_people = Person.project(graph)

# Override with a specific node list
some_people = Person.project(graph, select=Nodes(EX.alice, EX.bob))

# Override with a custom SPARQL query
active_people = Person.project(graph, select=Sparql("SELECT ?this WHERE { ?this ex:active true }"))
```

## Inheritance

Subclasses inherit the parent's selector unless they define their own:

```python
class Person(RDFModel, select=OfType(FOAF.Person)):
    ...

class Student(RDFModel):  # inherits OfType(FOAF.Person)
    ...
```

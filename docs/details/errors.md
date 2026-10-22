# Errors and Validation

Validation is handled entirely by Pydantic. Projection failures surface as typed exceptions carrying graph context.

## Exception hierarchy

All library errors inherit from `SemanticError`:

```
SemanticError
├── ProjectionError
├── CardinalityError
└── CycleError
```

## ProjectionError

Raised when a node cannot be projected into a model instance.

| Attribute | Type | Description |
|---|---|---|
| `node` | `Any` | The RDF node that failed (innermost for nested failures) |
| `model` | `type` | The model class being built |
| `field` | `str \| None` | The failing field name, if known |
| `cause` | `BaseException` | Underlying exception (often a Pydantic `ValidationError`) |
| `path` | `tuple` | Steps from root to this node: `((parent_node, field_name), ...)` |

### Handling errors with try_project

Instead of catching exceptions, use `try_project()` to collect errors:

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import RDFModel, Prop, Id, OfType


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

result = Person.try_project(graph)

for person in result.objects:
    print(person.name)

for error in result.errors:
    print(
        f"Failed to project {error.node} ({error.model.__name__}): {error.cause}"
    )
    if error.field:
        print(f"  Field: {error.field}")
    if error.path:
        print(f"  Path: {error.path}")
```

`ProjectionResult` has two attributes:

| Attribute | Type | Description |
|---|---|---|
| `objects` | `list[T]` | Successfully projected instances |
| `errors` | `list[ProjectionError]` | Collected projection errors |

## CardinalityError

A field expecting at most one value received several. This is raised when `on_many="error"` (the default).

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import RDFModel, Prop, Id, OfType, ProjectionError


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)  # expects exactly one


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ;
    foaf:name "Alice" , "Alyssa" .
""",
    format="turtle",
)

try:
    people = Person.project(graph)
except ProjectionError as e:
    print(f"Projection failed: {e.cause}")
```

To avoid this, use `on_many="first"` or `on_many="last"`:

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import RDFModel, Prop, Id, OfType


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name, on_many="first")


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ;
    foaf:name "Alice" , "Alyssa" .
""",
    format="turtle",
)

people = Person.project(graph)
print(f"Name (first): {people[0].name}")
```

Or use a list type annotation:

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import RDFModel, Prop, Id, OfType


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    names: list[str] = Prop(FOAF.name)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ;
    foaf:name "Alice" , "Alyssa" .
""",
    format="turtle",
)

people = Person.project(graph)
print(f"Names: {people[0].names}")
```

## CycleError

A node was re-entered while it was still being projected. Cycles are **detected and raised**, not resolved.

```python exec="on" source="above"
from rdflib import Graph, FOAF
from semantic_sugar import RDFModel, Prop, Id, OfType, ProjectionError


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    knows: "Person" = Prop(FOAF.knows)


# Alice knows Bob, Bob knows Alice — a cycle
graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.org/alice> a foaf:Person ; foaf:name "Alice" ; foaf:knows <http://example.org/bob> .
<http://example.org/bob> a foaf:Person ; foaf:name "Bob" ; foaf:knows <http://example.org/alice> .
""",
    format="turtle",
)

try:
    people = Person.project(graph)
except ProjectionError as e:
    print(f"Cycle detected: {e.cause}")
```
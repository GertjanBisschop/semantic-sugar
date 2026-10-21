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

```python
result = Person.try_project(graph)

for person in result.objects:
    print(person.name)

for error in result.errors:
    print(f"Failed to project {error.node} ({error.model.__name__}): {error.cause}")
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

```python
from semantic_sugar import CardinalityError

try:
    people = Person.project(graph)
except CardinalityError as e:
    print(f"Multiple values for a scalar field: {e}")
```

To avoid this, use `on_many="first"` or `on_many="last"`:

```python
name: str = Prop(FOAF.name, on_many="first")
```

Or use a list type annotation:

```python
names: list[str] = Prop(FOAF.name)
```

## CycleError

A node was re-entered while it was still being projected. Cycles are **detected and raised**, not resolved.

```python
from semantic_sugar import CycleError

try:
    people = Person.project(graph)
except CycleError as e:
    print(f"Cyclic reference detected at node {e.node}")
```

### Breaking cycles

Use one of these strategies:

- **`deref=False`** — Keep the reference as a raw `URIRef`/`BNode` instead of projecting:

  ```python
  knows: URIRef | None = Prop(FOAF.knows, deref=False)
  ```

- **`max_depth=`** — Limit nesting depth:

  ```python
  people = Person.project(graph, max_depth=2)
  ```

## Pydantic validation errors

Since `RDFModel` extends Pydantic's `BaseModel`, standard validation errors propagate as the `cause` of a `ProjectionError`:

```python
from pydantic import field_validator

class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    age: int = Prop(EX.age)

    @field_validator("age")
    @classmethod
    def positive_age(cls, v):
        if v < 0:
            raise ValueError("age must be positive")
        return v

# Validation failure is wrapped in ProjectionError
result = Person.try_project(graph)
for error in result.errors:
    if isinstance(error.cause, pydantic.ValidationError):
        print(f"Validation failed: {error.cause}")
```

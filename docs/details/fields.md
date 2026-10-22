# Field Derivation

Field derivation maps model fields to values extracted from RDF nodes. It uses type annotations for cardinality and `Prop(...)` expressions for the data source.

## Cardinality via type annotations

Cardinality is declared once through standard Python type hints:

| Annotation | Meaning |
|---|---|
| `T` | Exactly one value (required) |
| `T \| None` | Zero or one value (optional) |
| `list[T]` / `set[T]` | Zero or more values |

```python
name: str  # required — exactly one
title: str | None  # optional — zero or one
emails: list[str]  # multi-valued — zero or more
tags: set[str]  # multi-valued, no duplicates
```

## Prop

`Prop(source, **options)` declares how a field is derived from the graph. It returns a Pydantic `FieldInfo` with a `PropSpec` in its metadata, so all standard `pydantic.Field` options (`alias`, `description`, `default`, `default_factory`, etc.) still work.

### Source expressions

The `source` argument accepts several forms:

| Expression | Meaning |
|---|---|
| `FOAF.name` | Single predicate |
| `EX.a / EX.b` | Sequence path (rdflib path operators) |
| `FOAF.mbox \| FOAF.mail` | Alternative path |
| `~FOAF.knows` | Inverse path |
| `EX.parent * "+"` | Transitive path (also `"*"`, `"?"`) |
| `Sparql("SELECT ?v WHERE {...}")` | SPARQL expression; `?this` is pre-bound to the current node, results come from `?v` |
| `lambda graph, node: ...` | Arbitrary callable returning a node, value, iterable, or `None` |

```python
from rdflib import FOAF, Namespace
from semantic_sugar import Id, OfType, Prop, RDFModel, Sparql

EX = Namespace("http://example.org/")


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    emails: list[str] = Prop(FOAF.mbox | FOAF.mail)  # alternative predicates
    employer_name: str | None = Prop(EX.worksFor / EX.name)  # path
    colleagues: list[str] = Prop(EX.worksFor / ~EX.worksFor / FOAF.name)
    age: int = Prop(
        Sparql(
            "SELECT ?v WHERE { ?this ex:birthYear ?y . BIND(2026 - ?y AS ?v) }"
        )
    )
```

### Prop options

All options are keyword-only:

| Option | Type | Default | Description |
|---|---|---|---|
| `lang` | `str` \| `Lang` \| `None` | `None` | Language filter; shorthand `"en"` means `Lang.only("en")` |
| `datatype` | `URIRef` \| `None` | `None` | Filter literals by datatype IRI |
| `order_by` | predicate \| path \| `None` | `None` | Sort values by evaluating this predicate on each value |
| `deref` | `bool` | `True` | If `False`, keep nested nodes as raw `URIRef`/`BNode` instead of projecting them |
| `on_many` | `"error"` \| `"first"` \| `"last"` | `"error"` | How to handle multiple values for a scalar field |
| `default` | any | undefined | Pydantic default value |
| `default_factory` | callable \| `None` | `None` | Pydantic default factory |

Plus any other `pydantic.Field` keyword argument (`alias`, `description`, `examples`, etc.).

#### `on_many` behavior

When a scalar field (non-list) receives multiple values from the graph:

- `"error"` (default) — raises `CardinalityError`
- `"first"` — uses the first value found
- `"last"` — uses the last value found

```python
title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
```

#### `deref` behavior

By default, when a field points to another node that has an `RDFModel` type, the projector recursively projects that node into a nested model instance. Set `deref=False` to keep the raw reference:

```python
from rdflib import URIRef


class Dataset(RDFModel, select=OfType(DCAT.Dataset)):
    iri: Id
    # Nested — projects the distribution node into a Distribution instance
    distributions: tuple[Distribution, ...] = Prop(
        DCAT.distribution, deref=True
    )
    # Raw reference — keeps the URIRef
    access_service_uri: URIRef | None = Prop(DCAT.accessService, deref=False)
```

## Id

`Id` marks a field to receive the RDF node's own identifier (its IRI or blank node). It is a type alias: `Annotated[URIRef | BNode, IdMarker()]`.

```python
from semantic_sugar import Id


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id  # receives the node's IRI
```

A model can have at most one `Id` field.

## Lang

`Lang` controls language filtering for literal values (non-literals always pass through).

| Factory | Behavior |
|---|---|
| `Lang.only("en", "nl")` | Keep only literals tagged with the given languages |
| `Lang.prefer("nl", "en")` | Use the first language that has any value; untagged literals are the last resort |

```python
from semantic_sugar import Lang, Prop

# Only English values
name: str = Prop(FOAF.name, lang=Lang.only("en"))

# Prefer Dutch, fall back to English, then untagged
name: str = Prop(FOAF.name, lang=Lang.prefer("nl", "en"))

# Shorthand — equivalent to Lang.only("en")
name: str = Prop(FOAF.name, lang="en")
```

## Fields without Prop or Id

Model fields without `Prop` or `Id` are ignored by the projector. Pydantic still validates them — give them defaults:

```python
class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    computed_field: str = "default"  # not projected, but validated by Pydantic
```

## Pydantic validators

Since `RDFModel` extends Pydantic's `BaseModel`, all standard validators work:

```python
from pydantic import field_validator


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    age: int = Prop(EX.age)

    @field_validator("age")
    @classmethod
    def adult(cls, v):
        if v < 18:
            raise ValueError("underage")
        return v
```

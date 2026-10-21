# `semantic-sugar`: projecting RDF graphs onto Pydantic models

Project any RDF graph into validated, nested Pydantic models through four separable stages: **Selection**, **Derivation**, **Projection**, and **Validation**.

```python
from rdflib import FOAF, Namespace
from semantic_sugar import RDFModel, Prop, Id, Lang, OfType

EX = Namespace("http://example.org/")

class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name, lang=Lang.prefer("en"))
    emails: list[str] = Prop(FOAF.mbox)

people = Person.project(graph)  # list[Person]
```

---

## How it works

Every projection passes through four independent stages:

| # | Stage | Question | Mechanism |
|---|---|---|---|
| 1 | **Selection** | Which RDF nodes are processed? | `select=` class keyword, overridable per call |
| 2 | **Derivation** | Which values come from each node? | `Prop(...)` field expressions |
| 3 | **Projection** | How are values assembled into objects? | Type annotations + projector / row grouper |
| 4 | **Validation** | Does the object satisfy the consumer? | Plain Pydantic validators |

An `RDFModel` is a `BaseModel`. Validators, aliases, config, JSON schema, and serialization all work unchanged. Projection builds a raw dict and calls `model_validate`; it never reimplements validation.

Cardinality is declared once via type annotations:
- `T` — exactly one value (required)
- `T | None` — zero or one value (optional)
- `list[T]` / `set[T]` — zero or more values

---

## API Reference

### Declaring a model

```python
from rdflib import FOAF, Namespace
from pydantic import field_validator
from semantic_sugar import RDFModel, Prop, Id, Lang, OfType, Sparql

EX = Namespace("http://example.org/")

class Company(RDFModel, select=OfType(EX.Company)):
    iri: Id                                        # the node's own IRI / blank node
    name: str = Prop(EX.name)

class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name, lang=Lang.prefer("nl", "en"))
    emails: list[str] = Prop(FOAF.mbox)
    employer: Company | None = Prop(EX.worksFor)   # optional, nested projection
    colleagues: list[str] = Prop(
        EX.worksFor / ~EX.worksFor / FOAF.name,    # rdflib path expression
        lang="en"
    )
    age: int = Prop(
        Sparql("SELECT ?v WHERE { ?this ex:birthYear ?y . BIND(2026 - ?y AS ?v) }")
    )

    @field_validator("age")
    @classmethod
    def adult(cls, v):
        if v < 18: raise ValueError("underage")
        return v
```

Fields without `Prop` or `Id` are ignored by the projector. Pydantic still validates them — give them defaults.

---

### Selectors (Stage 1)

The `select=` class keyword determines which RDF nodes are projected. It can be overridden per call.

| Selector | Meaning |
|---|---|
| `OfType(*classes, infer=False)` | Nodes with `rdf:type` in `classes`; `infer=True` follows `rdfs:subClassOf` |
| `Sparql("SELECT ?this WHERE {...}")` | Query must bind `?this` to selected nodes |
| `Nodes(*nodes)` | Explicit list (strings become `URIRef`) |
| `FromCallable(fn)` | `fn(graph) -> Iterable[Node]` |
| `a & b` | Intersection of two selectors |
| `a \| b` | Union of two selectors |

`select=` also accepts a plain list of nodes or a callable. Subclasses inherit the parent's selector unless they set their own.

Per-call override:
```python
Person.project(graph, select=Nodes(EX.alice, EX.bob))
Person.project(graph, select=Sparql("SELECT ?this WHERE { ?this ex:active true }"))
```

#### `Selector` (ABC)

Base class for all selectors. Implement `select(self, graph: Graph) -> Iterator[Node]`.

#### `OfType(*classes: URIRef, infer: bool = False)`

Selects nodes typed as one of the given classes. With `infer=True`, it also follows `rdfs:subClassOf` transitivity (expensive on large graphs).

#### `Sparql(query: str, *, this: str = "this", value: str = "v", init_ns: dict | None = None)`

A SPARQL SELECT used either as a selector (must bind `?this`) or as a value derivation (must bind `?v`, with `?this` pre-bound to the current node). Prefixes bound on the graph are available without declaration.

#### `Nodes(*nodes: Node | str)`

Returns an explicit list of nodes. String arguments are converted to `URIRef`.

#### `FromCallable(fn: Callable[[Graph], Iterable[Node]])`

Wraps a callable that receives the graph and yields nodes.

#### `AllOf(*parts: Selector)` / `AnyOf(*parts: Selector)`

Intersection and union combinators. Also available via `&` and `|` operators on any `Selector`.

---

### Field derivation (Stage 2)

#### `Prop(source, **options)`

Declares how a model field is derived from the graph. Returns a Pydantic `FieldInfo` with a `PropSpec` in its metadata, so all `pydantic.Field` options (`alias`, `description`, `default`, `default_factory`, etc.) still work.

**`source`** is one of:

| Expression | Meaning |
|---|---|
| `FOAF.name` | Single predicate |
| `EX.a / EX.b` | Sequence path (rdflib path operators) |
| `FOAF.mbox \| FOAF.mail` | Alternative path |
| `~FOAF.knows` | Inverse path |
| `EX.parent * "+"` | Transitive path (also `"*"`, `"?"`) |
| `Sparql("SELECT ?v WHERE {...}")` | `?this` is pre-bound; results come from `?v` |
| `lambda graph, node: ...` | Arbitrary callable returning a node, value, iterable, or `None` |

**Options** (all keyword-only):

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

#### `Id`

Type alias: `Annotated[URIRef | BNode, IdMarker()]`. Marks a field to receive the RDF node's own identifier.

#### `Lang`

Language policy for literal values (non-literals always pass through).

| Factory | Behavior |
|---|---|
| `Lang.only("en", "nl")` | Keep only literals tagged with the given languages |
| `Lang.prefer("nl", "en")` | Use the first language that has any value; untagged literals are the last resort |

---

### Graph-driven projection (Stage 3a)

Project nodes from an RDF graph into model instances.

#### `Model.project(graph, **opts) -> list[Self]`

Project all selected nodes. Returns a list.

| Parameter | Default | Description |
|---|---|---|
| `select` | `None` | Override the class-level selector |
| `on_error` | `"raise"` | `"raise"` to stop on first error, `"skip"` to skip failing nodes |
| `max_depth` | `None` | Maximum nesting depth; nested fields beyond this depth are treated as empty |
| `identity_map` | `True` | Same node + model → same Python object within a run |

#### `Model.iter_project(graph, **opts) -> Iterator[Self]`

Lazy version of `project()`. Yields instances one at a time.

#### `Model.try_project(graph, **opts) -> ProjectionResult[Self]`

Never raises per-node errors. Returns a `ProjectionResult` with `.objects` (successful instances) and `.errors` (collected `ProjectionError` instances).

#### `Model.project_one(graph, node, *, max_depth=None) -> Self`

Project a single node, ignoring the selector. `node` can be a `Node` or a string (converted to `URIRef`).

---

### Query-driven projection (Stage 3b)

A SPARQL SELECT returns a flat table. Rows are grouped by key; multi-valued fields aggregate across the group.

#### `Model.from_rows(rows, *, key=None, bind=None, on_error="raise") -> list[Self]`

Project from SPARQL result rows. Three levels of control:

**Level 1: Naming convention** (default). Variable names map to field names using `__` as the nesting separator. The `Id` variable is used as the group key.

```python
rows = graph.query("""
    SELECT ?iri ?name ?emails ?employer__iri ?employer__name WHERE { ... }
""")
people = Person.from_rows(rows)
```

**Level 2: Explicit binding**. Map variables to fields explicitly with dotted paths for nesting.

```python
people = Person.from_rows(
    rows,
    key="p",
    bind={
        "name": "n",
        "emails": "e",
        "employer.iri": "c",
        "employer.name": "cn"
    }
)
```

**Level 3: Reusable `Projection` object**. Full control, decoupled from the model's `Prop` declarations.

```python
from semantic_sugar import Projection, Var

by_company = Projection(
    Person,
    key=Var("p"),
    query="SELECT ?p ?n ?c ?cn ?e WHERE { ... }",
    fields={
        "iri": Var("p"),
        "name": Var("n"),
        "emails": Var("e"),
        "employer": Projection(
            Company,
            key=Var("c"),
            fields={"iri": Var("c"), "name": Var("cn")}
        )
    }
)
people = by_company.run(graph)
# or
people = by_company.from_rows(rows)
```

#### `Projection` dataclass

| Field | Type | Description |
|---|---|---|
| `model` | `type` | Target `RDFModel` subclass |
| `fields` | `dict[str, Any]` | Field name → `Var`, `str`, or nested `Projection` |
| `key` | `Var` \| `str` \| `None` | Variable identifying one object; rows sharing it are merged |
| `query` | `str` \| `None` | Optional SPARQL query for `run()` |

**Methods:**

- `Projection.by_bind(model, bind, key=None, strict=True)` — Build from explicit variable bindings.
- `Projection.by_convention(model, variables, sep="__")` — Build from variable names using the `__` convention.
- `Projection.run(graph, **init_bindings)` — Execute the query and project results.
- `Projection.from_rows(rows, on_error="raise")` — Project from pre-fetched rows.

#### `Var(name: str)`

Frozen dataclass referencing a SPARQL result variable.

**Rules for query-driven mode:**
- Unmapped `list` fields become `[]`; unmapped optionals become `None`.
- Rows whose key is unbound (e.g. an empty `OPTIONAL`) contribute nothing to that nested object.
- With no `key`, grouping falls back to the tuple of all directly bound variables.
- `Prop` filters (`lang`, `datatype`, `order_by`) do **not** apply in query-driven mode — the query is responsible for filtering.
- `CONSTRUCT`/`DESCRIBE` results are graphs: pass them to `Model.project()`, not `from_rows()`.

---

### Validation & Errors (Stage 4)

Validation is handled entirely by Pydantic. Projection failures surface as typed exceptions carrying graph context.

#### `ProjectionError`

Raised when a node cannot be projected into a model instance.

| Attribute | Type | Description |
|---|---|---|
| `node` | `Any` | The RDF node that failed (innermost for nested failures) |
| `model` | `type` | The model class being built |
| `field` | `str \| None` | The failing field name, if known |
| `cause` | `BaseException` | Underlying exception (often a Pydantic `ValidationError`) |
| `path` | `tuple` | Steps from root to this node: `((parent_node, field_name), ...)` |

#### `CardinalityError`

A field expecting at most one value received several. Raised when `on_many="error"` (the default).

#### `CycleError`

A node was re-entered while it was still being projected. Cycles are **detected and raised**, not resolved.

#### `ProjectionResult[T]`

Generic dataclass returned by `try_project()`.

| Field | Type | Description |
|---|---|---|
| `objects` | `list[T]` | Successfully projected instances |
| `errors` | `list[ProjectionError]` | Collected projection errors |

#### `semanticError`

Base class for all library errors (`CardinalityError`, `CycleError`, `ProjectionError`).

---

### Value conversion

#### `Converters`

Pluggable RDF term → Python value conversion, keyed by datatype IRI.

| Method | Description |
|---|---|
| `register(datatype: URIRef, fn: Callable[[Literal], Any])` | Register a custom converter for a datatype |
| `convert(term: Any) -> Any` | Convert a term: literals become Python values, IRIs and blank nodes pass through |

Default behavior:
- Literals with a registered datatype → custom converter
- Literals with a language tag → plain `str` (language tag dropped)
- Other literals → `Literal.toPython()`
- IRIs and blank nodes → passed through unchanged

#### `default_converters`

The global `Converters` singleton used by the projector. Customize it:

```python
from rdflib import XSD, Namespace
from semantic_sugar import default_converters

default_converters.register(XSD.duration, lambda lit: parse_duration(str(lit)))
```

---

### `RDFModel` class details

#### Class variables

| Variable | Type | Description |
|---|---|---|
| `model_config` | `ConfigDict` | `arbitrary_types_allowed=True` so `URIRef`/`BNode` fields work |
| `__rdf_projectable__` | `bool` | Marker used internally to detect nested models |
| `__rdf_select__` | `Selector \| None` | Class-level selector (set via `select=` keyword) |

#### Class methods

| Method | Description |
|---|---|
| `rdf_plan()` | Returns the cached field plan (lazy, built on first use) |
| `project(graph, **opts)` | Project all selected nodes |
| `iter_project(graph, **opts)` | Lazy projection iterator |
| `try_project(graph, **opts)` | Projection with error collection |
| `project_one(graph, node, **opts)` | Project a single node |
| `from_rows(rows, **opts)` | Query-driven projection from SPARQL rows |

---

## Known Limitations

The following limitations are inherent to the current implementation:

### Cycles are not supported

If the graph contains a cycle (e.g. Person A knows Person B who knows Person A), projection raises `CycleError`. Workarounds:
- Use `Prop(..., deref=False)` to break the cycle by keeping the reference as a raw `URIRef`/`BNode`.
- Use `max_depth=` to limit nesting depth.

There is no automatic cycle resolution with placeholders or lazy references.

### No polymorphism

A field annotated as `Student | Teacher` cannot be resolved automatically. The projector uses the element type directly; union types with multiple model candidates are not dispatched based on `rdf:type`.

### No `strict_type` checking

When projecting a nested node, the library does not verify that the node actually matches the nested model's `select` predicate. A mismatched node will simply produce missing fields.

### No SHACL/Shape validation

The library does not integrate with `pyshacl` or provide graph-level shape validation. A `Shape(...)` selector is not yet implemented.

### No `ns=` class keyword

There is no shorthand namespace keyword. Every `Prop` source must be a fully-qualified `URIRef` or path expression.

### Remote endpoint performance

The graph-driven projector issues per-node lookups (`graph.objects()`). This is efficient for in-memory graphs but causes N+1 query patterns against remote SPARQL endpoints. Batched query planning is not yet implemented.

### `Sparql` derivation and `initBindings`

`Sparql` derivations rely on rdflib's `initBindings` parameter, which can behave unexpectedly with certain subquery scoping patterns. If a query fails, try substituting `?this` textually in the query string instead.

### Query-driven mode limitations

- `Prop` filters (`lang`, `datatype`, `order_by`) are **not applied** in query-driven mode. The SPARQL query itself must handle filtering.
- `CONSTRUCT` and `DESCRIBE` results cannot be passed to `from_rows()` — use `Model.project()` on the result graph instead.

### Unmapped fields

Model fields without `Prop` or `Id` are never populated by projection. They must have Pydantic defaults or be optional.

---

## Future Work (TODO)

The following features are planned but not yet implemented:

1. **Cycle support** — Build with placeholders and patch, or provide lazy nested references so cyclic graphs can be projected without errors.
2. **`strict_type=True` on `Prop`** — Verify that a nested node matches the nested model's `select` before projecting.
3. **Polymorphism** — Resolve `Student | Teacher` union types by matching each class's `select` against the node's `rdf:type`.
4. **`Shape(...)` selector** — Filter nodes by SHACL conformance via optional `pyshacl` integration.
5. **`validate_graph=` option** — Run SHACL validation before or after projection.
6. **Remote-endpoint query planning** — Compile a model into batched SELECT/CONSTRUCT queries per nesting level to avoid N+1 patterns.
7. **Reverse direction** — `to_graph()` for invertible expressions; `to_shacl()`, `to_sparql()`; model inference from data.
8. **`ns=` class keyword** — Shorthand so bare fields default to `ns[field_name]`.
9. **More comprehensive tests** — Coverage for `bind=`, `Projection` (Level 3), `on_many`, `max_depth`, `deref=False`, `order_by`, `Lang.only`, blank-node IDs, forward references, and model inheritance.

---

## Example

```python
from rdflib import FOAF, Graph, Namespace
from pydantic import field_validator
from semantic_sugar import Id, Lang, OfType, Prop, RDFModel, Sparql

EX = Namespace("http://example.org/")

class Company(RDFModel, select=OfType(EX.Company)):
    iri: Id
    name: str = Prop(EX.name)

class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name, lang=Lang.prefer("nl", "en"))
    emails: list[str] = Prop(FOAF.mbox)
    employer: Company | None = Prop(EX.worksFor)
    colleagues: list[str] = Prop(EX.worksFor / ~EX.worksFor / FOAF.name, lang="en")
    age: int = Prop(
        Sparql("SELECT ?v WHERE { ?this ex:birthYear ?y . BIND(2026 - ?y AS ?v) }")
    )

    @field_validator("age")
    @classmethod
    def adult(cls, v):
        if v < 18: raise ValueError("underage")
        return v

# Graph-driven projection with error collection
graph = Graph().parse("data.ttl", format="turtle")
result = Person.try_project(graph)

for person in result.objects:
    print(person.name, person.employer.name if person.employer else "unemployed")

for error in result.errors:
    print(f"Skipped {error.node}: {error.cause}")

# Query-driven projection
rows = graph.query("""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX ex: <http://example.org/>
    SELECT ?iri ?name ?emails ?employer__iri ?employer__name WHERE {
        ?iri a foaf:Person ; foaf:name ?name .
        FILTER(lang(?name) = 'en')
        OPTIONAL { ?iri foaf:mbox ?emails }
        OPTIONAL { ?iri ex:worksFor ?employer__iri .
                   ?employer__iri ex:name ?employer__name }
    }
""")
people = Person.from_rows(rows)
```

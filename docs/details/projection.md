# Projection

Projection assembles RDF data into model instances. `semantic-sugar` supports two modes: **graph-driven** (traverses the RDF graph directly) and **query-driven** (groups flat SPARQL result rows).

## Graph-driven projection

The graph-driven projector traverses the RDF graph, following `Prop` predicates and recursively projecting nested models.

### project

Project all selected nodes into a list of model instances:

```python
from rdflib import Graph
from semantic_sugar.ontologies.dcat import Catalog

graph = Graph().parse("catalog.ttl", format="turtle")
catalogs = Catalog.project(graph)
```

| Parameter | Default | Description |
|---|---|---|
| `select` | `None` | Override the class-level selector |
| `on_error` | `"raise"` | `"raise"` to stop on first error, `"skip"` to skip failing nodes |
| `max_depth` | `None` | Maximum nesting depth; nested fields beyond this depth are treated as empty |
| `identity_map` | `True` | Same node + model → same Python object within a run |

### iter_project

Lazy version that yields instances one at a time:

```python
for catalog in Catalog.iter_project(graph):
    print(catalog.title)
```

### try_project

Never raises per-node errors. Returns a `ProjectionResult` with successful instances and collected errors:

```python
result = Catalog.try_project(graph)

for catalog in result.objects:
    print(catalog.title)

for error in result.errors:
    print(f"Skipped {error.node}: {error.cause}")
```

### project_one

Project a single node, ignoring the selector. Useful when you already know the target node:

```python
from rdflib import URIRef

person = Person.project_one(graph, URIRef("http://example.org/alice"))
```

`node` can be a `Node` or a string (converted to `URIRef`).

## Query-driven projection

A SPARQL SELECT returns a flat table. Query-driven projection groups rows by key and aggregates multi-valued fields across each group.

### from_rows

```python
rows = graph.query("""
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

Three levels of control:

**Level 1: Naming convention** (default). Variable names map to field names using `__` as the nesting separator. The `Id` variable is used as the group key.

**Level 2: Explicit binding**. Map variables to fields explicitly with dotted paths for nesting:

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

**Level 3: Reusable `Projection` object**. Full control, decoupled from the model's `Prop` declarations:

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

### Projection helpers

- `Projection.by_bind(model, bind, key=None, strict=True)` — Build from explicit variable bindings.
- `Projection.by_convention(model, variables, sep="__")` — Build from variable names using the `__` convention.
- `Projection.run(graph, **init_bindings)` — Execute the query and project results.
- `Projection.from_rows(rows, on_error="raise")` — Project from pre-fetched rows.

### Query-driven mode rules

- Unmapped `list` fields become `[]`; unmapped optionals become `None`.
- Rows whose key is unbound (e.g., an empty `OPTIONAL`) contribute nothing to that nested object.
- With no `key`, grouping falls back to the tuple of all directly bound variables.
- `Prop` filters (`lang`, `datatype`, `order_by`) do **not** apply in query-driven mode — the query itself is responsible for filtering.
- `CONSTRUCT`/`DESCRIBE` results are graphs: pass them to `Model.project()`, not `from_rows()`.

## Choosing a mode

| Use case | Recommended mode |
|---|---|
| Small to medium in-memory graphs | Graph-driven (`project`) |
| Complex nested structures | Graph-driven (`project`) |
| Large remote SPARQL endpoints | Query-driven (`from_rows`) |
| Fine-grained control over queries | Query-driven (`Projection`) |
| Ad-hoc queries with known shape | Query-driven (`from_rows` with `bind`) |

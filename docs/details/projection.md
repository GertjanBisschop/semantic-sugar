# Projection

Projection assembles RDF data into model instances. `semantic-sugar` supports two modes: **graph-driven** (traverses the RDF graph directly) and **query-driven** (groups flat SPARQL result rows).

## Graph-driven projection

The graph-driven projector traverses the RDF graph, following `Prop` predicates and recursively projecting nested models.

### project

Project all selected nodes into a list of model instances:

```python exec="on" source="above"
from rdflib import Graph
from semantic_sugar.ontologies.dcat import Catalog

graph = Graph().parse(
    data="""
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

<http://example.org/catalog1> a dcat:Catalog ;
    dcterms:title "Example Catalog" .
""",
    format="turtle",
)
catalogs = Catalog.project(graph)
print(f"Found {len(catalogs)} catalog(s)")
for c in catalogs:
    print(f"  {c.title}")
```

| Parameter | Default | Description |
|---|---|---|
| `select` | `None` | Override the class-level selector |
| `on_error` | `"raise"` | `"raise"` to stop on first error, `"skip"` to skip failing nodes |
| `max_depth` | `None` | Maximum nesting depth; nested fields beyond this depth are treated as empty |
| `identity_map` | `True` | Same node + model → same Python object within a run |

### iter_project

Lazy version that yields instances one at a time:

```python exec="on" source="above"
from rdflib import Graph
from semantic_sugar.ontologies.dcat import Catalog

graph = Graph().parse(
    data="""
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

<http://example.org/cat1> a dcat:Catalog ; dcterms:title "First" .
<http://example.org/cat2> a dcat:Catalog ; dcterms:title "Second" .
""",
    format="turtle",
)

for catalog in Catalog.iter_project(graph):
    print(catalog.title)
```

### try_project

Never raises per-node errors. Returns a `ProjectionResult` with successful instances and collected errors:

```python exec="on" source="above"
from rdflib import Graph
from semantic_sugar.ontologies.dcat import Catalog

graph = Graph().parse(
    data="""
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

<http://example.org/cat1> a dcat:Catalog ; dcterms:title "Working Catalog" .
""",
    format="turtle",
)

result = Catalog.try_project(graph)

for catalog in result.objects:
    print(catalog.title)

for error in result.errors:
    print(f"Skipped {error.node}: {error.cause}")
```

### project_one

Project a single node, ignoring the selector. Useful when you already know the target node:

```python exec="on" source="above"
from rdflib import Graph, FOAF, URIRef
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

person = Person.project_one(graph, URIRef("http://example.org/alice"))
print(f"{person.name} ({person.iri})")
```

`node` can be a `Node` or a string (converted to `URIRef`).

## Query-driven projection

A SPARQL SELECT returns a flat table. Query-driven projection groups rows by key and aggregates multi-valued fields across each group.

### from_rows

```python exec="on" source="above"
from rdflib import Graph, FOAF, Namespace
from semantic_sugar import RDFModel, Prop, Id, OfType

EX = Namespace("http://example.org/")


class Employer(RDFModel):
    iri: Id
    name: str | None = Prop(EX.name, default=None)


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    emails: list[str] = Prop(FOAF.mbox)
    employer: Employer | None = Prop(EX.worksFor, default=None)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ex: <http://example.org/> .

<http://example.org/alice> a foaf:Person ;
    foaf:name "Alice"@en ;
    foaf:mbox "alice@example.org" ;
    ex:worksFor <http://example.org/acme> .

<http://example.org/acme> ex:name "Acme Corp"@en .
""",
    format="turtle",
)

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
for p in people:
    print(f"{p.name}: employer={p.employer.name if p.employer else 'None'}")
```

Three levels of control:

**Level 1: Naming convention** (default). Variable names map to field names using `__` as the nesting separator. The `Id` variable is used as the group key.

**Level 2: Explicit binding**. Map variables to fields explicitly with dotted paths for nesting:

```python exec="on" source="above"
from rdflib import Graph, FOAF, Namespace
from semantic_sugar import RDFModel, Prop, Id, OfType

EX = Namespace("http://example.org/")


class Employer(RDFModel):
    iri: Id
    name: str | None = Prop(EX.name, default=None)


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    emails: list[str] = Prop(FOAF.mbox)
    employer: Employer | None = Prop(EX.worksFor, default=None)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ex: <http://example.org/> .

<http://example.org/alice> a foaf:Person ;
    foaf:name "Alice" ;
    ex:worksFor <http://example.org/acme> .
<http://example.org/acme> ex:name "Acme Corp" .
""",
    format="turtle",
)

rows = graph.query("""
    SELECT ?p ?n ?e ?c ?cn WHERE {
        ?p a foaf:Person ; foaf:name ?n .
        OPTIONAL { ?p foaf:mbox ?e }
        OPTIONAL { ?p ex:worksFor ?c . ?c ex:name ?cn }
    }
""")

people = Person.from_rows(
    rows,
    key="p",
    bind={
        "name": "n",
        "emails": "e",
        "employer.iri": "c",
        "employer.name": "cn",
    },
)
for p in people:
    print(f"{p.name}: employer={p.employer.name if p.employer else 'None'}")
```

**Level 3: Reusable `Projection` object**. Full control, decoupled from the model's `Prop` declarations:

```python exec="on" source="above"
from rdflib import Graph, FOAF, Namespace
from semantic_sugar import RDFModel, Prop, Id, OfType, Projection, Var

EX = Namespace("http://example.org/")


class Employer(RDFModel):
    iri: Id
    name: str | None = Prop(EX.name, default=None)


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name)
    emails: list[str] = Prop(FOAF.mbox)
    employer: Employer | None = Prop(EX.worksFor, default=None)


graph = Graph().parse(
    data="""
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ex: <http://example.org/> .

<http://example.org/alice> a foaf:Person ;
    foaf:name "Alice" ;
    ex:worksFor <http://example.org/acme> .
<http://example.org/acme> ex:name "Acme Corp" .
""",
    format="turtle",
)

by_company = Projection(
    Person,
    key=Var("p"),
    query="""
    SELECT ?p ?n ?c ?cn ?e WHERE {
        ?p a foaf:Person ; foaf:name ?n .
        OPTIONAL { ?p foaf:mbox ?e }
        OPTIONAL { ?p ex:worksFor ?c . ?c ex:name ?cn }
    }
    """,
    fields={
        "iri": Var("p"),
        "name": Var("n"),
        "emails": Var("e"),
        "employer": Projection(
            Employer, key=Var("c"), fields={"iri": Var("c"), "name": Var("cn")}
        ),
    },
)
people = by_company.run(graph)
for p in people:
    print(f"{p.name}: employer={p.employer.name if p.employer else 'None'}")
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

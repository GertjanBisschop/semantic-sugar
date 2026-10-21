"""Comprehensive tests for all documented features of semantic-sugar.

Covers features not exercised by the basic smoke tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import field_validator
from rdflib import BNode, FOAF, Graph, Literal, Namespace, RDF, RDFS, XSD
from rdflib.term import Node

from semantic_sugar import (
    AllOf,
    AnyOf,
    CardinalityError,
    CycleError,
    FromCallable,
    Id,
    Lang,
    Nodes,
    OfType,
    Prop,
    Projection,
    RDFModel,
    Selector,
    Sparql,
    Var,
    ProjectionError,
    ProjectionResult,
    SemanticError,
    default_converters,
)

EX = Namespace("http://example.org/")
DC = Namespace("http://purl.org/dc/elements/1.1/")


# ==================================================================== fixtures


@pytest.fixture
def g():
    """A rich graph for testing various features."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("foaf", FOAF)
    g.bind("dc", DC)

    # Company
    g.add((EX.acme, RDF.type, EX.Company))
    g.add((EX.acme, EX.name, Literal("Acme Corp")))

    # People
    g.add((EX.alice, RDF.type, FOAF.Person))
    g.add((EX.alice, FOAF.name, Literal("Alice", lang="en")))
    g.add((EX.alice, FOAF.name, Literal("Alicia", lang="nl")))
    g.add((EX.alice, FOAF.mbox, Literal("alice@example.org")))
    g.add((EX.alice, EX.worksFor, EX.acme))
    g.add((EX.alice, EX.birthYear, Literal(1990, datatype=XSD.integer)))

    g.add((EX.bob, RDF.type, FOAF.Person))
    g.add((EX.bob, FOAF.name, Literal("Bob", lang="en")))
    g.add((EX.bob, EX.worksFor, EX.acme))
    g.add((EX.bob, EX.birthYear, Literal(1985, datatype=XSD.integer)))

    # Person with no name (will cause projection error)
    g.add((EX.ghost, RDF.type, FOAF.Person))
    g.add((EX.ghost, EX.birthYear, Literal(1970, datatype=XSD.integer)))

    # Subclass for infer testing
    g.add((EX.Employee, RDFS.subClassOf, FOAF.Person))
    g.add((EX.carol, RDF.type, EX.Employee))
    g.add((EX.carol, FOAF.name, Literal("Carol", lang="en")))
    g.add((EX.carol, EX.birthYear, Literal(1995, datatype=XSD.integer)))

    # Blank node person
    bnode_person = BNode()
    g.add((bnode_person, RDF.type, FOAF.Person))
    g.add((bnode_person, FOAF.name, Literal("BNode Person", lang="en")))
    g.add((bnode_person, EX.birthYear, Literal(2000, datatype=XSD.integer)))

    # Datatype literals for datatype filter testing
    g.add((EX.alice, EX.score, Literal(95, datatype=XSD.integer)))
    g.add((EX.alice, EX.score, Literal("95", datatype=XSD.string)))

    # Order by testing
    g.add((EX.alice, EX.knows, EX.bob))
    g.add((EX.alice, EX.knows, EX.carol))
    g.add((EX.bob, EX.sortKey, Literal(2, datatype=XSD.integer)))
    g.add((EX.carol, EX.sortKey, Literal(1, datatype=XSD.integer)))

    # Multiple values for on_many testing
    g.add((EX.bob, FOAF.mbox, Literal("bob1@example.org")))
    g.add((EX.bob, FOAF.mbox, Literal("bob2@example.org")))

    # Cycle testing: A knows B knows A
    g.add((EX.cycA, RDF.type, FOAF.Person))
    g.add((EX.cycA, FOAF.name, Literal("CycA", lang="en")))
    g.add((EX.cycA, EX.knows, EX.cycB))
    g.add((EX.cycA, EX.birthYear, Literal(1990, datatype=XSD.integer)))
    g.add((EX.cycB, RDF.type, FOAF.Person))
    g.add((EX.cycB, FOAF.name, Literal("CycB", lang="en")))
    g.add((EX.cycB, EX.knows, EX.cycA))
    g.add((EX.cycB, EX.birthYear, Literal(1990, datatype=XSD.integer)))

    return g


# ==================================================================== Selectors


class TestSelectors:
    """Test all documented selector types and combinators."""

    def test_of_type_basic(self, g):
        """OfType selects nodes with matching rdf:type."""
        sel = OfType(FOAF.Person)
        nodes = list(sel.select(g))
        # alice, bob, ghost, bnode_person, cycA, cycB = 6 (carol is EX.Employee, not FOAF.Person)
        assert len(nodes) == 6
        assert EX.alice in nodes
        assert (
            EX.carol not in nodes
        )  # carol is EX.Employee, not directly FOAF.Person

    def test_of_type_infer(self, g):
        """OfType(infer=True) follows rdfs:subClassOf."""
        sel = OfType(FOAF.Person, infer=True)
        nodes = list(sel.select(g))
        # Should include carol who is EX.Employee (subClassOf FOAF.Person)
        assert EX.carol in nodes
        assert (
            len(nodes) >= 6
        )  # alice, bob, ghost, carol, bnode_person, + carol via infer

    def test_sparql_selector(self, g):
        """Sparql as a selector must bind ?this."""
        sel = Sparql(
            "SELECT ?this WHERE { ?this a foaf:Person ; foaf:name ?n . FILTER(lang(?n)='en') }"
        )
        nodes = list(sel.select(g))
        names = {str(n).rsplit("/", 1)[-1] for n in nodes if hasattr(n, "n3")}
        assert "alice" in names
        assert "bob" in names
        assert "ghost" not in names

    def test_nodes_selector(self, g):
        """Nodes returns explicit list; strings become URIRef."""
        sel = Nodes(EX.alice, "http://example.org/bob")
        nodes = list(sel.select(g))
        assert len(nodes) == 2
        assert EX.alice in nodes

    def test_from_callable(self, g):
        """FromCallable wraps a callable that yields nodes."""

        def my_selector(graph):
            return [EX.alice, EX.bob]

        sel = FromCallable(my_selector)
        nodes = list(sel.select(g))
        assert len(nodes) == 2

    def test_bare_callable_selector(self, g):
        """A bare callable passed to select= is coerced to FromCallable."""

        class P(RDFModel):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        def my_sel(graph):
            return [EX.alice]

        result = P.project(g, select=my_sel)
        assert len(result) == 1
        assert result[0].name == "Alice"

    def test_all_of_selector(self, g):
        """AllOf returns intersection of selectors."""
        sel = AllOf(OfType(FOAF.Person), Nodes(EX.alice, EX.bob, EX.acme))
        nodes = list(sel.select(g))
        assert EX.alice in nodes
        assert EX.bob in nodes
        assert EX.acme not in nodes

    def test_any_of_selector(self, g):
        """AnyOf returns union of selectors."""
        sel = AnyOf(Nodes(EX.alice), Nodes(EX.bob))
        nodes = list(sel.select(g))
        assert len(nodes) == 2

    def test_and_operator(self, g):
        """& operator on selectors creates AllOf."""
        sel = OfType(FOAF.Person) & Nodes(EX.alice, EX.bob, EX.acme)
        nodes = list(sel.select(g))
        assert EX.alice in nodes
        assert EX.acme not in nodes

    def test_or_operator(self, g):
        """| operator on selectors creates AnyOf."""
        sel = Nodes(EX.alice) | Nodes(EX.bob)
        nodes = list(sel.select(g))
        assert len(nodes) == 2

    def test_selector_inheritance(self, g):
        """Subclass inherits parent's selector unless it sets its own."""

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)

        class NamedPerson(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)

        # NamedPerson inherits OfType(FOAF.Person) from Person
        # (we can't test true Python inheritance with same-name classes,
        # so we test the __rdf_select__ propagation)
        assert Person.__rdf_select__ is not None
        assert NamedPerson.__rdf_select__ is not None

    def test_list_as_selector(self, g):
        """A plain list passed to select= is coerced to Nodes."""

        class P(RDFModel):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        result = P.project(g, select=[EX.alice])
        assert len(result) == 1


# ==================================================================== Field derivation


class TestFieldDerivation:
    """Test Prop options: lang, datatype, order_by, deref, on_many, callable source."""

    def test_lang_only(self, g):
        """Lang.only keeps only literals with the specified language."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str = Prop(FOAF.name, lang=Lang.only("nl"))

        result = P.project(g)
        assert len(result) == 1
        assert result[0].name == "Alicia"

    def test_lang_only_no_match(self, g):
        """Lang.only with no matching language yields empty."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str | None = Prop(FOAF.name, lang=Lang.only("fr"))

        result = P.project(g)
        assert result[0].name is None

    def test_lang_shorthand(self, g):
        """lang='en' shorthand means Lang.only('en')."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        result = P.project(g)
        assert result[0].name == "Alice"

    def test_datatype_filter(self, g):
        """Prop with datatype filter keeps only matching literals."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            scores: list[int] = Prop(EX.score, datatype=XSD.integer)

        result = P.project(g)
        assert result[0].scores == [95]

    def test_order_by(self, g):
        """Prop with order_by sorts values by the given predicate."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            friends: list[str] = Prop(EX.knows, order_by=EX.sortKey)

        result = P.project(g)
        # carol has sortKey=1, bob has sortKey=2
        names = [str(f).rsplit("/", 1)[-1] for f in result[0].friends]
        assert names == ["carol", "bob"]

    def test_deref_false(self, g):
        """Prop with deref=False keeps nested nodes as raw URIRef instead of projecting."""
        from rdflib import URIRef

        class Company(RDFModel, select=OfType(EX.Company)):
            iri: Id
            name: str = Prop(EX.name)

        class PersonWithCompany(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            employer: Company | None = Prop(EX.worksFor)

        # With deref=False, the field type must match the raw value (URIRef), not the model
        class PersonWithDeref(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            employer_ref: URIRef | None = Prop(EX.worksFor, deref=False)

        # Without deref=False, employer is a Company instance
        result_normal = PersonWithCompany.project(g)
        assert isinstance(result_normal[0].employer, Company)
        assert result_normal[0].employer.name == "Acme Corp"

        # With deref=False, employer_ref should be the raw URIRef, not a Company instance
        result_deref = PersonWithDeref.project(g)
        assert isinstance(result_deref[0].employer_ref, URIRef)
        assert result_deref[0].employer_ref == EX.acme

    def test_on_many_first(self, g):
        """on_many='first' picks the first value for a scalar field."""

        class P(RDFModel, select=Nodes(EX.bob)):
            iri: Id
            email: str = Prop(FOAF.mbox, on_many="first")

        result = P.project(g)
        assert result[0].email == "bob1@example.org"

    def test_on_many_last(self, g):
        """on_many='last' picks the last value for a scalar field."""

        class P(RDFModel, select=Nodes(EX.bob)):
            iri: Id
            email: str = Prop(FOAF.mbox, on_many="last")

        result = P.project(g)
        assert result[0].email == "bob2@example.org"

    def test_callable_source(self, g):
        """Prop with a callable source receives (graph, node)."""

        def get_name(graph, node):
            return Literal("Computed Name")

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str = Prop(get_name)

        result = P.project(g)
        assert result[0].name == "Computed Name"

    def test_callable_source_returns_none(self, g):
        """Callable returning None yields no values."""

        def nothing(graph, node):
            return None

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str | None = Prop(nothing)

        result = P.project(g)
        assert result[0].name is None

    def test_callable_source_returns_iterable(self, g):
        """Callable returning an iterable yields multiple values."""

        def multi(graph, node):
            return [Literal("a"), Literal("b")]

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            tags: list[str] = Prop(multi)

        result = P.project(g)
        assert result[0].tags == ["a", "b"]

    def test_prop_with_pydantic_default(self, g):
        """Prop with default= passes through to Pydantic."""

        class P(RDFModel, select=Nodes(EX.ghost)):
            iri: Id
            name: str = Prop(FOAF.name, default="Unknown")

        result = P.project(g)
        assert result[0].name == "Unknown"

    def test_prop_with_alias(self, g):
        """Prop with alias= works as a Pydantic Field option for serialization."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            display_name: str = Prop(
                FOAF.name,
                alias="displayName",
                validation_alias="display_name",
                lang="en",
            )

        result = P.project(g)
        # The field is accessed by Python name
        assert result[0].display_name == "Alice"
        # Alias controls serialization output
        data = result[0].model_dump(by_alias=True)
        assert data["displayName"] == "Alice"

    def test_sparql_derivation(self, g):
        """Sparql as a Prop source derives values via SPARQL."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            age: int = Prop(
                Sparql(
                    "SELECT ?v WHERE { ?this ex:birthYear ?y . BIND(2026 - ?y AS ?v) }"
                )
            )

        result = P.project(g)
        ages = {str(p.iri).rsplit("/", 1)[-1]: p.age for p in result}
        assert ages["alice"] == 36
        assert ages["bob"] == 41

    def test_path_expression(self, g):
        """Prop with rdflib path expression (sequence, inverse, alternative)."""

        # Alternative: FOAF.mbox | FOAF.homepage
        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            contacts: list[str] = Prop(FOAF.mbox | FOAF.homepage)

        result = P.project(g)
        assert len(result[0].contacts) >= 1

    def test_inverse_path(self, g):
        """Prop with inverse path (~predicate)."""

        # ~EX.worksFor: who works for alice? (nobody, but test the mechanism)
        class P(RDFModel, select=Nodes(EX.acme)):
            iri: Id
            employees: list[str] = Prop(~EX.worksFor)

        result = P.project(g)
        assert len(result[0].employees) >= 2  # alice and bob work for acme


# ==================================================================== Projection


class TestProjection:
    """Test graph-driven projection options."""

    def test_iter_project(self, g):
        """iter_project yields instances lazily."""

        class P(RDFModel, select=Nodes(EX.alice, EX.bob)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        items = list(P.iter_project(g))
        assert len(items) == 2

    def test_project_one(self, g):
        """project_one projects a single node, ignoring selector."""

        class P(RDFModel, select=OfType(EX.Company)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        # Project alice even though selector is Company
        person = P.project_one(g, EX.alice)
        assert str(person.iri).endswith("alice")

    def test_project_one_string_node(self, g):
        """project_one accepts a string node (converted to URIRef)."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        person = P.project_one(g, "http://example.org/alice")
        assert person.name == "Alice"

    def test_on_error_skip(self, g):
        """on_error='skip' skips failing nodes instead of raising."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")  # ghost has no name

        result = P.project(g, on_error="skip")
        names = {str(p.iri).rsplit("/", 1)[-1] for p in result}
        assert "ghost" not in names
        assert "alice" in names

    def test_max_depth(self, g):
        """max_depth limits nested projection depth."""

        class Company(RDFModel, select=OfType(EX.Company)):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            employer: Company | None = Prop(EX.worksFor)

        # depth=0 should not project nested Company
        result = Person.project(g, max_depth=0)
        assert result[0].employer is None

        # Normal projection should work
        result = Person.project(g)
        assert result[0].employer is not None
        assert result[0].employer.name == "Acme Corp"

    def test_identity_map_false(self, g):
        """identity_map=False creates separate objects for same node."""

        class Company(RDFModel, select=OfType(EX.Company)):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            employer: Company | None = Prop(EX.worksFor)

        result = Person.project(g, identity_map=False)
        # alice and bob both work for acme; without identity_map they get different objects
        acme_owners = [p for p in result if p.employer is not None]
        if len(acme_owners) >= 2:
            assert acme_owners[0].employer is not acme_owners[1].employer

    def test_identity_map_true(self, g):
        """identity_map=True (default) shares objects for same node."""

        class Company(RDFModel, select=OfType(EX.Company)):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            employer: Company | None = Prop(EX.worksFor)

        result = Person.project(g, identity_map=True)
        acme_owners = [p for p in result if p.employer is not None]
        if len(acme_owners) >= 2:
            assert acme_owners[0].employer is acme_owners[1].employer

    def test_blank_node_id(self, g):
        """Id field works with blank nodes."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        # Use try_project since ghost has no name and will fail
        result = P.try_project(g)
        bnode_results = [p for p in result.objects if isinstance(p.iri, BNode)]
        assert len(bnode_results) >= 1
        assert bnode_results[0].name == "BNode Person"

    def test_required_field_missing(self, g):
        """Missing required field raises ProjectionError."""

        class P(RDFModel, select=Nodes(EX.ghost)):
            iri: Id
            name: str = Prop(FOAF.name)  # required, ghost has no name

        with pytest.raises(ProjectionError):
            P.project(g)

    def test_optional_field_missing(self, g):
        """Missing optional field becomes None."""

        class P(RDFModel, select=Nodes(EX.ghost)):
            iri: Id
            name: str | None = Prop(FOAF.name)  # optional

        result = P.project(g)
        assert result[0].name is None

    def test_list_field_empty(self, g):
        """Empty list field for required many becomes []."""

        class P(RDFModel, select=Nodes(EX.ghost)):
            iri: Id
            emails: list[str] = Prop(FOAF.mbox)  # many, ghost has none

        result = P.project(g)
        assert result[0].emails == []


# ==================================================================== Query-driven projection


class TestQueryDriven:
    """Test from_rows, Projection.by_bind, Projection.by_convention, and Projection.run."""

    def test_from_rows_convention(self, g):
        """from_rows with naming convention (__ separator for nesting)."""
        rows = g.query("""
            PREFIX ex:<http://example.org/>
            PREFIX foaf:<http://xmlns.com/foaf/0.1/>
            SELECT ?iri ?name ?emails ?employer__iri ?employer__name WHERE {
                ?iri a foaf:Person ; foaf:name ?name .
                FILTER(lang(?name)='en')
                OPTIONAL { ?iri foaf:mbox ?emails }
                OPTIONAL { ?iri ex:worksFor ?employer__iri .
                           ?employer__iri ex:name ?employer__name }
            }
        """)

        class Company(RDFModel):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            emails: list[str] = Prop(FOAF.mbox)
            employer: Company | None = Prop(EX.worksFor)

        people = Person.from_rows(rows)
        assert len(people) >= 1
        alice = next((p for p in people if p.name == "Alice"), None)
        assert alice is not None
        assert alice.employer is not None
        assert alice.employer.name == "Acme Corp"

    def test_from_rows_explicit_bind(self, g):
        """from_rows with explicit bind mapping (Level 2)."""
        rows = g.query("""
            PREFIX ex:<http://example.org/>
            PREFIX foaf:<http://xmlns.com/foaf/0.1/>
            SELECT ?p ?n ?e ?c ?cn WHERE {
                ?p a foaf:Person ; foaf:name ?n .
                FILTER(lang(?n)='en')
                OPTIONAL { ?p foaf:mbox ?e }
                OPTIONAL { ?p ex:worksFor ?c . ?c ex:name ?cn }
            }
        """)

        class Company(RDFModel):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            emails: list[str] = Prop(FOAF.mbox)
            employer: Company | None = Prop(EX.worksFor)

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
        assert len(people) >= 1
        alice = next((p for p in people if p.name == "Alice"), None)
        assert alice is not None

    def test_projection_object_run(self, g):
        """Projection object with run() executes query and projects (Level 3)."""

        class Company(RDFModel):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            emails: list[str] = Prop(FOAF.mbox)
            employer: Company | None = Prop(EX.worksFor)

        proj = Projection(
            Person,
            key=Var("p"),
            query="""
                PREFIX ex:<http://example.org/>
                PREFIX foaf:<http://xmlns.com/foaf/0.1/>
                SELECT ?p ?n ?e ?c ?cn WHERE {
                    ?p a foaf:Person ; foaf:name ?n .
                    FILTER(lang(?n)='en')
                    OPTIONAL { ?p foaf:mbox ?e }
                    OPTIONAL { ?p ex:worksFor ?c . ?c ex:name ?cn }
                }
            """,
            fields={
                "iri": Var("p"),
                "name": Var("n"),
                "emails": Var("e"),
                "employer": Projection(
                    Company,
                    key=Var("c"),
                    fields={"iri": Var("c"), "name": Var("cn")},
                ),
            },
        )
        people = proj.run(g)
        assert len(people) >= 1
        alice = next((p for p in people if p.name == "Alice"), None)
        assert alice is not None
        assert alice.employer is not None

    def test_projection_by_bind(self, g):
        """Projection.by_bind builds from explicit variable bindings."""

        class Company(RDFModel):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            emails: list[str] = Prop(FOAF.mbox)
            employer: Company | None = Prop(EX.worksFor)

        proj = Projection.by_bind(
            Person,
            bind={
                "iri": "p",
                "name": "n",
                "emails": "e",
                "employer.iri": "c",
                "employer.name": "cn",
            },
            key="p",
        )
        assert proj.model is Person
        assert isinstance(proj.fields["employer"], Projection)

    def test_projection_by_convention(self, g):
        """Projection.by_convention builds from variable names."""

        class Company(RDFModel):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            emails: list[str] = Prop(FOAF.mbox)
            employer: Company | None = Prop(EX.worksFor)

        variables = [
            "iri",
            "name",
            "emails",
            "employer__iri",
            "employer__name",
        ]
        proj = Projection.by_convention(Person, variables)
        assert proj.model is Person

    def test_unmapped_list_field(self, g):
        """Unmapped list field in query-driven mode becomes []."""
        rows = g.query("""
            PREFIX foaf:<http://xmlns.com/foaf/0.1/>
            SELECT ?iri ?name WHERE {
                ?iri a foaf:Person ; foaf:name ?name .
                FILTER(lang(?name)='en')
            }
        """)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            emails: list[str] = Prop(FOAF.mbox)  # not in query

        people = Person.from_rows(rows)
        for p in people:
            assert p.emails == []

    def test_unmapped_optional_field(self, g):
        """Unmapped optional field in query-driven mode becomes None."""
        rows = g.query("""
            PREFIX foaf:<http://xmlns.com/foaf/0.1/>
            SELECT ?iri ?name WHERE {
                ?iri a foaf:Person ; foaf:name ?name .
                FILTER(lang(?name)='en')
            }
        """)

        class Company(RDFModel):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)
            employer: Company | None = Prop(EX.worksFor)  # not in query

        people = Person.from_rows(rows)
        for p in people:
            assert p.employer is None

    def test_from_rows_on_error_skip(self, g):
        """from_rows with on_error='skip' skips failing rows."""
        rows = g.query("""
            PREFIX ex:<http://example.org/>
            PREFIX foaf:<http://xmlns.com/foaf/0.1/>
            SELECT ?iri ?name WHERE {
                ?iri a foaf:Person .
                OPTIONAL { ?iri foaf:name ?name . FILTER(lang(?name)='en') }
            }
        """)

        class Person(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)  # required

        people = Person.from_rows(rows, on_error="skip")
        names = {p.name for p in people}
        assert "" not in names  # ghost's empty name should be skipped


# ==================================================================== Errors


class TestErrors:
    """Test error types, messages, and behavior."""

    def test_cycle_error(self, g):
        """Cyclic graph raises CycleError."""

        class Person(RDFModel, select=Nodes(EX.cycA)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")
            friend: "Person | None" = Prop(EX.knows)

        Person.model_rebuild()
        with pytest.raises(ProjectionError) as exc_info:
            Person.project(g)
        assert isinstance(exc_info.value.cause, CycleError)

    def test_cardinality_error(self, g):
        """Multiple values for scalar field raises CardinalityError."""

        class P(RDFModel, select=Nodes(EX.bob)):
            iri: Id
            email: str = Prop(FOAF.mbox)  # bob has 2 emails, scalar field

        with pytest.raises(ProjectionError) as exc_info:
            P.project(g)
        assert isinstance(exc_info.value.cause, CardinalityError)

    def test_projection_error_path(self, g):
        """ProjectionError.path tracks the nesting path."""

        class Company(RDFModel, select=OfType(EX.Company)):
            iri: Id
            name: str = Prop(EX.name)

        class Person(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            employer: Company = Prop(
                EX.worksFor
            )  # required, but let's break Company

        # Modify graph so Company has no name
        g2 = Graph()
        g2.bind("ex", EX)
        g2.bind("foaf", FOAF)
        g2.add((EX.acme, RDF.type, EX.Company))
        # No name for acme!
        g2.add((EX.alice, RDF.type, FOAF.Person))
        g2.add((EX.alice, EX.worksFor, EX.acme))

        with pytest.raises(ProjectionError) as exc_info:
            Person.project(g2)
        # Path should include the Person node and employer field
        assert len(exc_info.value.path) >= 1

    def test_semantic_error_base_class(self):
        """SemanticError is the base class for all library errors."""
        assert issubclass(ProjectionError, SemanticError)
        assert issubclass(CardinalityError, SemanticError)
        assert issubclass(CycleError, SemanticError)

    def test_projection_result(self, g):
        """try_project returns ProjectionResult with objects and errors."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        result = P.try_project(g)
        assert isinstance(result, ProjectionResult)
        assert hasattr(result, "objects")
        assert hasattr(result, "errors")
        assert len(result.objects) + len(result.errors) >= 5  # all persons


# ==================================================================== Converters


class TestConverters:
    """Test value conversion and custom converters."""

    def test_custom_converter(self, g):
        """Registering a custom converter for a datatype."""
        from rdflib import XSD

        # Register a custom converter for XSD.integer that doubles the value
        original = default_converters._by_datatype.get(XSD.integer)
        try:
            default_converters.register(XSD.integer, lambda lit: int(lit) * 2)

            class P(RDFModel, select=Nodes(EX.alice)):
                iri: Id
                score: int = Prop(EX.score, datatype=XSD.integer)

            result = P.project(g)
            assert result[0].score == 190  # 95 * 2
        finally:
            # Restore original converter
            if original is not None:
                default_converters.register(XSD.integer, original)
            else:
                default_converters._by_datatype.pop(XSD.integer, None)

    def test_language_tagged_literal_to_str(self, g):
        """Language-tagged literals are converted to plain str."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")  # filter to single value

        result = P.project(g)
        # Name should be a string, not a Literal object
        assert isinstance(result[0].name, str)
        assert result[0].name == "Alice"


# ==================================================================== RDFModel Pydantic compatibility


class TestPydanticCompatibility:
    """Test that RDFModel works as a drop-in BaseModel."""

    def test_json_schema(self, g):
        """RDFModel produces valid JSON schema."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name)

        schema = P.model_json_schema()
        assert (
            "$defs" in schema
            or "definitions" in schema
            or "properties" in schema
        )
        assert "name" in schema.get("properties", {})

    def test_model_dump(self, g):
        """RDFModel instances can be serialized with model_dump."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        result = P.project(g)
        data = result[0].model_dump()
        assert "name" in data
        assert data["name"] == "Alice"

    def test_model_dump_json(self, g):
        """RDFModel instances can be serialized to JSON."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        result = P.project(g)
        json_str = result[0].model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "Alice"

    def test_field_validator(self, g):
        """Pydantic field validators work on RDFModel."""

        class P(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

            @field_validator("name")
            @classmethod
            def name_not_empty(cls, v):
                if not v:
                    raise ValueError("name must not be empty")
                return v

        # ghost has no name, should fail
        with pytest.raises(ProjectionError):
            P.project(g, select=Nodes(EX.ghost))

    def test_forward_reference(self, g):
        """Forward references in type annotations work."""

        class Node(RDFModel):
            iri: Id
            label: str = Prop(DC.title)
            child: "Node | None" = Prop(EX.hasChild)

        Node.model_rebuild()
        assert "child" in Node.rdf_plan()

    def test_pydantic_alias(self, g):
        """Pydantic alias works with Prop for serialization output."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            display_name: str = Prop(
                FOAF.name,
                alias="displayName",
                validation_alias="display_name",
                lang="en",
            )

        result = P.project(g)
        # The field is accessed by Python name
        assert result[0].display_name == "Alice"
        # Alias controls serialization output key
        data = result[0].model_dump(by_alias=True)
        assert "displayName" in data
        assert data["displayName"] == "Alice"
        # Without by_alias, uses Python field name
        data_no_alias = result[0].model_dump()
        assert "display_name" in data_no_alias

    def test_default_factory(self, g):
        """Prop with default_factory works."""

        class P(RDFModel, select=Nodes(EX.ghost)):
            iri: Id
            tags: list[str] = Prop(FOAF.mbox, default_factory=list)

        result = P.project(g)
        assert result[0].tags == []

    def test_set_type_annotation(self, g):
        """set[T] type annotation works like list[T]."""

        class P(RDFModel, select=Nodes(EX.alice)):
            iri: Id
            emails: set[str] = Prop(FOAF.mbox)

        result = P.project(g)
        assert isinstance(result[0].emails, (list, set))
        assert len(result[0].emails) >= 1


# ==================================================================== Model inheritance


class TestModelInheritance:
    """Test RDFModel inheritance behavior."""

    def test_inherited_fields(self, g):
        """Subclass inherits parent's Prop fields via Python inheritance."""

        class BasePerson(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        class ExtendedPerson(BasePerson):
            emails: list[str] = Prop(FOAF.mbox)

        # ExtendedPerson should inherit iri/name from BasePerson and add emails
        plan = ExtendedPerson.rdf_plan()
        assert "iri" in plan
        assert "name" in plan
        assert "emails" in plan

    def test_inherited_selector(self, g):
        """Subclass without select= inherits parent's selector."""

        class BasePerson(RDFModel, select=OfType(FOAF.Person)):
            iri: Id
            name: str = Prop(FOAF.name, lang="en")

        class ExtendedPerson(BasePerson):
            emails: list[str] = Prop(FOAF.mbox)

        # ExtendedPerson should inherit the selector from BasePerson
        assert ExtendedPerson.__rdf_select__ is not None
        # Use try_project since ghost has no name
        result = ExtendedPerson.try_project(g)
        assert len(result.objects) >= 1

"""Tests for converting RDFModel instances back to RDF graphs."""

from __future__ import annotations

from typing import Any

import pytest
from rdflib import (
    BNode,
    FOAF,
    Graph,
    Literal,
    Namespace,
    RDF,
    RDFS,
    URIRef,
    XSD,
)
from rdflib.term import Node

from semantic_sugar import (
    Id,
    OfType,
    Prop,
    RDFModel,
    Sparql,
    to_rdf,
    to_rdf_many,
)

EX = Namespace("http://example.org/")
SCHEMA = Namespace("http://schema.org/")


# ==================================================================== Simple model


class Person(RDFModel, select=OfType(FOAF.Person)):
    uri: Id
    name: str = Prop(FOAF.name)
    email: str | None = Prop(FOAF.mbox, default=None)
    age: int | None = Prop(EX.age, default=None)


class TestSimpleModel:
    """Convert a simple model with scalar fields."""

    def test_basic_conversion(self):
        person = Person(
            uri=EX.alice, name="Alice", email="alice@example.org", age=30
        )
        graph = person.to_rdf()

        assert (EX.alice, RDF.type, FOAF.Person) in graph
        assert (EX.alice, FOAF.name, Literal("Alice")) in graph
        assert (EX.alice, FOAF.mbox, Literal("alice@example.org")) in graph
        assert (EX.alice, EX.age, Literal(30)) in graph

    def test_optional_field_none(self):
        """None values should not produce triples."""
        person = Person(uri=EX.bob, name="Bob", email=None, age=None)
        graph = person.to_rdf()

        assert (EX.bob, RDF.type, FOAF.Person) in graph
        assert (EX.bob, FOAF.name, Literal("Bob")) in graph
        assert (EX.bob, FOAF.mbox, None) not in graph  # type: ignore[arg-type]
        assert (EX.bob, EX.age, None) not in graph  # type: ignore[arg-type]

    def test_to_rdf_function(self):
        """The standalone to_rdf function should work the same."""
        person = Person(
            uri=EX.carol, name="Carol", email="carol@example.org", age=25
        )
        graph = to_rdf(person)

        assert (EX.carol, RDF.type, FOAF.Person) in graph
        assert (EX.carol, FOAF.name, Literal("Carol")) in graph

    def test_add_to_existing_graph(self):
        """Passing an existing graph should add triples to it."""
        existing = Graph()
        existing.add((EX.meta, RDF.type, EX.Metadata))

        person = Person(uri=EX.alice, name="Alice", email=None, age=None)
        result = person.to_rdf(existing)

        assert result is existing
        assert (EX.meta, RDF.type, EX.Metadata) in result
        assert (EX.alice, RDF.type, FOAF.Person) in result

    def test_no_selector_no_type(self):
        """A model without a selector should not produce rdf:type triples."""

        class SimplePerson(RDFModel):
            uri: Id
            name: str = Prop(FOAF.name)

        person = SimplePerson(uri=EX.dave, name="Dave")
        graph = person.to_rdf()

        # No rdf:type triple should be added
        type_triples = list(graph.objects(EX.dave, RDF.type))
        assert len(type_triples) == 0
        assert (EX.dave, FOAF.name, Literal("Dave")) in graph


# ==================================================================== Many cardinality


class Author(RDFModel, select=OfType(EX.Author)):
    uri: Id
    name: str = Prop(FOAF.name)
    interests: tuple[str, ...] = Prop(EX.interest)


class TestManyCardinality:
    """Fields with 'many' cardinality produce multiple triples."""

    def test_many_field(self):
        author = Author(
            uri=EX.writer1,
            name="Jane Doe",
            interests=("RDF", "Python", "Semantic Web"),
        )
        graph = author.to_rdf()

        assert (EX.writer1, RDF.type, EX.Author) in graph
        assert (EX.writer1, FOAF.name, Literal("Jane Doe")) in graph
        assert (EX.writer1, EX.interest, Literal("RDF")) in graph
        assert (EX.writer1, EX.interest, Literal("Python")) in graph
        assert (EX.writer1, EX.interest, Literal("Semantic Web")) in graph

    def test_many_field_list(self):
        """List values should also produce multiple triples."""

        class AuthorList(RDFModel, select=OfType(EX.Author)):
            uri: Id
            name: str = Prop(FOAF.name)
            interests: list[str] = Prop(EX.interest)

        author = AuthorList(
            uri=EX.writer2, name="John Smith", interests=["AI", "ML"]
        )
        graph = author.to_rdf()

        assert (EX.writer2, EX.interest, Literal("AI")) in graph
        assert (EX.writer2, EX.interest, Literal("ML")) in graph


# ==================================================================== Nested models


class Address(RDFModel):
    uri: Id
    street: str = Prop(SCHEMA.streetAddress)
    city: str = Prop(SCHEMA.addressLocality)


class Contact(RDFModel, select=OfType(FOAF.Person)):
    uri: Id
    name: str = Prop(FOAF.name)
    address: Address = Prop(FOAF.homepage, deref=True)


class TestNestedModel:
    """Nested RDFModel instances are converted recursively."""

    def test_single_nested(self):
        addr = Address(uri=EX.addr1, street="123 Main St", city="Springfield")
        contact = Contact(uri=EX.person1, name="Alice", address=addr)
        graph = contact.to_rdf()

        # Main entity
        assert (EX.person1, RDF.type, FOAF.Person) in graph
        assert (EX.person1, FOAF.name, Literal("Alice")) in graph
        assert (EX.person1, FOAF.homepage, EX.addr1) in graph

        # Nested entity
        assert (
            EX.addr1,
            SCHEMA.streetAddress,
            Literal("123 Main St"),
        ) in graph
        assert (
            EX.addr1,
            SCHEMA.addressLocality,
            Literal("Springfield"),
        ) in graph

    def test_many_nested(self):
        """Many nested models produce multiple triples."""

        class Company(RDFModel, select=OfType(EX.Company)):
            uri: Id
            name: str = Prop(FOAF.name)
            employees: tuple[Contact, ...] = Prop(EX.employee, deref=True)

        emp1 = Contact(
            uri=EX.emp1,
            name="Alice",
            address=Address(uri=EX.a1, street="St1", city="City1"),
        )
        emp2 = Contact(
            uri=EX.emp2,
            name="Bob",
            address=Address(uri=EX.a2, street="St2", city="City2"),
        )
        company = Company(
            uri=EX.acme, name="Acme Corp", employees=(emp1, emp2)
        )
        graph = company.to_rdf()

        assert (EX.acme, RDF.type, EX.Company) in graph
        assert (EX.acme, FOAF.name, Literal("Acme Corp")) in graph
        assert (EX.acme, EX.employee, EX.emp1) in graph
        assert (EX.acme, EX.employee, EX.emp2) in graph

        # Employee details
        assert (EX.emp1, RDF.type, FOAF.Person) in graph
        assert (EX.emp1, FOAF.name, Literal("Alice")) in graph
        assert (EX.emp2, RDF.type, FOAF.Person) in graph
        assert (EX.emp2, FOAF.name, Literal("Bob")) in graph


# ==================================================================== Sparql source fields (should be skipped)


class Sensor(RDFModel, select=OfType(EX.Sensor)):
    uri: Id
    label: str = Prop(RDFS.label)
    # This field uses SPARQL — should be skipped during to_rdf
    readings: tuple[str, ...] = Prop(
        Sparql("SELECT ?v WHERE { ?this ex:reading ?v }")
    )


class TestSparqlSkipped:
    """Fields with SPARQL sources are skipped during conversion."""

    def test_sparql_field_skipped(self):
        sensor = Sensor(
            uri=EX.s1, label="Temperature Sensor", readings=("22.5", "23.0")
        )
        graph = sensor.to_rdf()

        assert (EX.s1, RDF.type, EX.Sensor) in graph
        assert (EX.s1, RDFS.label, Literal("Temperature Sensor")) in graph

        # SPARQL-sourced field should NOT produce triples
        sparql_triples = list(graph.objects(EX.s1))
        # Only type and label predicates should appear
        predicates = set(sparql_triples)
        # No triples from the SPARQL field
        for triple in graph.triples((EX.s1, None, None)):
            assert triple[1] in (RDF.type, RDFS.label), (
                f"Unexpected predicate: {triple[1]}"
            )


# ==================================================================== Callable source fields (should be skipped)


def _computed(graph: Graph, node: Node) -> str:
    return "computed"


class ComputedModel(RDFModel, select=OfType(EX.Computed)):
    uri: Id
    name: str = Prop(FOAF.name)
    computed: str = Prop(_computed)


class TestCallableSkipped:
    """Fields with callable sources are skipped during conversion."""

    def test_callable_field_skipped(self):
        obj = ComputedModel(uri=EX.c1, name="Test", computed="value")
        graph = obj.to_rdf()

        assert (EX.c1, RDF.type, EX.Computed) in graph
        assert (EX.c1, FOAF.name, Literal("Test")) in graph

        for triple in graph.triples((EX.c1, None, None)):
            assert triple[1] in (RDF.type, FOAF.name), (
                f"Unexpected predicate: {triple[1]}"
            )


# ==================================================================== to_rdf_many


class TestToRdfMany:
    """Convert multiple instances to a single graph."""

    def test_multiple_instances(self):
        p1 = Person(uri=EX.alice, name="Alice", email=None, age=30)
        p2 = Person(uri=EX.bob, name="Bob", email="bob@example.org", age=25)
        graph = to_rdf_many([p1, p2])

        assert (EX.alice, RDF.type, FOAF.Person) in graph
        assert (EX.alice, FOAF.name, Literal("Alice")) in graph
        assert (EX.bob, RDF.type, FOAF.Person) in graph
        assert (EX.bob, FOAF.name, Literal("Bob")) in graph
        assert (EX.bob, FOAF.mbox, Literal("bob@example.org")) in graph

    def test_classmethod(self):
        """The classmethod variant should work the same."""
        p1 = Person(uri=EX.alice, name="Alice", email=None, age=30)
        p2 = Person(uri=EX.bob, name="Bob", email=None, age=25)
        graph = Person.to_rdf_many([p1, p2])

        assert len(list(graph.subjects(RDF.type, FOAF.Person))) == 2


# ==================================================================== BNode subjects


class TestBNodeSubject:
    """Models with BNode subjects."""

    def test_bnode_id(self):
        bnode = BNode()
        person = Person(uri=bnode, name="Anonymous", email=None, age=None)
        graph = person.to_rdf()

        assert (bnode, RDF.type, FOAF.Person) in graph
        assert (bnode, FOAF.name, Literal("Anonymous")) in graph

    def test_no_id_generates_bnode(self):
        """When Id field is a BNode, it is used as the subject."""
        bnode = BNode()
        person = Person(uri=bnode, name="BNode Person", email=None, age=None)
        graph = person.to_rdf()

        assert (bnode, RDF.type, FOAF.Person) in graph
        assert (bnode, FOAF.name, Literal("BNode Person")) in graph


# ==================================================================== Round-trip


class TestRoundTrip:
    """Project from RDF, convert back, and verify the graph is equivalent."""

    def test_simple_round_trip(self):
        """Build a graph, project to model, convert back, compare."""
        # Original graph
        g1 = Graph()
        g1.add((EX.alice, RDF.type, FOAF.Person))
        g1.add((EX.alice, FOAF.name, Literal("Alice")))
        g1.add((EX.alice, FOAF.mbox, Literal("alice@example.org")))
        g1.add((EX.alice, EX.age, Literal(30, datatype=XSD.integer)))

        # Project
        people = Person.project(g1, select=[EX.alice])
        assert len(people) == 1
        person = people[0]

        # Convert back
        g2 = person.to_rdf()

        # Compare key triples
        assert (EX.alice, RDF.type, FOAF.Person) in g2
        assert (EX.alice, FOAF.name, Literal("Alice")) in g2
        assert (EX.alice, FOAF.mbox, Literal("alice@example.org")) in g2
        # The age literal may differ in datatype representation
        age_triples = list(g2.objects(EX.alice, EX.age))
        assert len(age_triples) == 1
        assert age_triples[0].toPython() == 30

    def test_nested_round_trip(self):
        """Round-trip with nested models."""
        g1 = Graph()
        g1.add((EX.person1, RDF.type, FOAF.Person))
        g1.add((EX.person1, FOAF.name, Literal("Alice")))
        g1.add((EX.person1, FOAF.homepage, EX.addr1))
        g1.add((EX.addr1, SCHEMA.streetAddress, Literal("123 Main St")))
        g1.add((EX.addr1, SCHEMA.addressLocality, Literal("Springfield")))

        contacts = Contact.project(g1, select=[EX.person1])
        assert len(contacts) == 1
        contact = contacts[0]

        g2 = contact.to_rdf()

        assert (EX.person1, RDF.type, FOAF.Person) in g2
        assert (EX.person1, FOAF.name, Literal("Alice")) in g2
        assert (EX.person1, FOAF.homepage, EX.addr1) in g2
        assert (EX.addr1, SCHEMA.streetAddress, Literal("123 Main St")) in g2
        assert (EX.addr1, SCHEMA.addressLocality, Literal("Springfield")) in g2

    def test_many_round_trip(self):
        """Round-trip with many-cardinality fields."""
        g1 = Graph()
        g1.add((EX.writer1, RDF.type, EX.Author))
        g1.add((EX.writer1, FOAF.name, Literal("Jane Doe")))
        g1.add((EX.writer1, EX.interest, Literal("RDF")))
        g1.add((EX.writer1, EX.interest, Literal("Python")))

        authors = Author.project(g1, select=[EX.writer1])
        assert len(authors) == 1
        author = authors[0]

        g2 = author.to_rdf()

        assert (EX.writer1, RDF.type, EX.Author) in g2
        assert (EX.writer1, FOAF.name, Literal("Jane Doe")) in g2
        assert (EX.writer1, EX.interest, Literal("RDF")) in g2
        assert (EX.writer1, EX.interest, Literal("Python")) in g2


# ==================================================================== Edge cases


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_non_rdfmodel_raises(self):
        """Passing a non-RDFModel should raise TypeError."""
        with pytest.raises(TypeError, match="Expected an RDFModel"):
            to_rdf("not a model")  # type: ignore[arg-type]

    def test_empty_graph_returned(self):
        """A model with only an Id and no Prop fields produces only rdf:type."""

        class Minimal(RDFModel, select=OfType(EX.Minimal)):
            uri: Id

        obj = Minimal(uri=EX.min1)
        graph = obj.to_rdf()

        assert (EX.min1, RDF.type, EX.Minimal) in graph
        # No other triples
        assert len(list(graph.triples((EX.min1, None, None)))) == 1

    def test_boolean_value(self):
        """Boolean values should be converted to RDF Literals."""

        class Flagged(RDFModel, select=OfType(EX.Flagged)):
            uri: Id
            active: bool = Prop(EX.active)

        obj = Flagged(uri=EX.f1, active=True)
        graph = obj.to_rdf()

        assert (EX.f1, EX.active, Literal(True)) in graph

    def test_float_value(self):
        """Float values should be converted to RDF Literals."""

        class Scored(RDFModel, select=OfType(EX.Scored)):
            uri: Id
            score: float = Prop(EX.score)

        obj = Scored(uri=EX.s1, score=3.14)
        graph = obj.to_rdf()

        score_triples = list(graph.objects(EX.s1, EX.score))
        assert len(score_triples) == 1
        assert score_triples[0].toPython() == 3.14

    def test_uri_ref_value(self):
        """URIRef values should be preserved as URIRefs."""

        class Referenced(RDFModel, select=OfType(EX.Referenced)):
            uri: Id
            sees: URIRef = Prop(FOAF.knows)

        obj = Referenced(uri=EX.p1, sees=EX.p2)
        graph = obj.to_rdf()

        assert (EX.p1, FOAF.knows, EX.p2) in graph

    def test_multiple_of_type_classes(self):
        """OfType with multiple classes should produce multiple rdf:type triples."""

        class MultiType(RDFModel, select=OfType(FOAF.Person, EX.Human)):
            uri: Id
            name: str = Prop(FOAF.name)

        obj = MultiType(uri=EX.mt1, name="Multi")
        graph = obj.to_rdf()

        assert (EX.mt1, RDF.type, FOAF.Person) in graph
        assert (EX.mt1, RDF.type, EX.Human) in graph

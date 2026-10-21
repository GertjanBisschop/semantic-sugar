import pytest
from pydantic import field_validator
from rdflib import FOAF, Graph, Namespace
from semantic_sugar import Id, Lang, OfType, Prop, RDFModel, Sparql

EX = Namespace("http://example.org/")
TTL = """
@prefix ex: <http://example.org/> . @prefix foaf: <http://xmlns.com/foaf/0.1/> .
ex:acme a ex:Company ; ex:name "Acme" .
ex:alice a foaf:Person ; foaf:name "Alice"@en, "Alicia"@nl ; foaf:mbox "a@x.org", "b@x.org" ;
         ex:worksFor ex:acme ; ex:birthYear 1990 .
ex:bob a foaf:Person ; foaf:name "Bob"@en ; ex:worksFor ex:acme ; ex:birthYear 2015 .
ex:eve a foaf:Person ; ex:birthYear 1980 .
"""


class Company(RDFModel, select=OfType(EX.Company)):
    iri: Id
    name: str = Prop(EX.name)


class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name, lang=Lang.prefer("nl", "en"))
    emails: list[str] = Prop(FOAF.mbox)
    employer: Company | None = Prop(EX.worksFor)
    colleagues: list[str] = Prop(EX.worksFor / ~EX.worksFor / FOAF.name, lang="en")
    age: int = Prop(Sparql("SELECT ?v WHERE { ?this ex:birthYear ?y . BIND(2026 - ?y AS ?v) }"))

    @field_validator("age")
    @classmethod
    def adult(cls, v):
        if v < 18: raise ValueError("underage")
        return v


@pytest.fixture
def g():
    return Graph().parse(data=TTL, format="turtle")


def test_project_and_collect(g):
    res = Person.try_project(g)
    names = {str(p.iri).rsplit("/", 1)[1]: p for p in res.objects}
    assert names["alice"].name == "Alicia" and names["alice"].emails == ["a@x.org", "b@x.org"]
    assert names["alice"].employer.name == "Acme" and names["alice"].age == 36
    assert sorted(names["alice"].colleagues) == ["Alice", "Bob"]
    bad = {str(e.node).rsplit("/", 1)[1] for e in res.errors}
    assert bad == {"bob", "eve"}            # underage; missing name


def test_override_selector(g):
    assert len(Person.project(g, select=[EX.alice])) == 1


def test_from_rows(g):
    rows = g.query("""PREFIX ex:<http://example.org/> PREFIX foaf:<http://xmlns.com/foaf/0.1/>
      SELECT ?iri ?name ?emails ?employer__iri ?employer__name ?age WHERE {
        ?iri foaf:name ?name ; ex:birthYear ?y . BIND(2026-?y AS ?age)
        FILTER(lang(?name)='en')
        OPTIONAL { ?iri foaf:mbox ?emails }
        OPTIONAL { ?iri ex:worksFor ?employer__iri . ?employer__iri ex:name ?employer__name } }""")
    people = Person.from_rows(rows, on_error="skip")
    assert len(people) == 1 and people[0].emails == ["a@x.org", "b@x.org"]
    assert people[0].employer.name == "Acme"

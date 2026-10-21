# `semantic-sugar`: RDF graph <-> Pydantic

Project any RDF graph into validated, nested Pydantic models through four separable stages: **Selection**, **Derivation**, **Projection**, and **Validation**.

```python
from rdflib import FOAF, Namespace, Graph
from semantic_sugar import RDFModel, Prop, Id, Lang, OfType

EX = Namespace("http://example.org/")

graph = """
@prefix ex:   <http://example.org/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

ex:alice
    a foaf:Person ;
    foaf:name "Alice Smith"@en ;
    foaf:name "Alice Smith"@fr ;
    foaf:mbox <mailto:alice@example.org> ;
    foaf:mbox <mailto:alice.smith@example.org> .

ex:bob
    a foaf:Person ;
    foaf:name "Bob Jones"@en ;
    foaf:mbox <mailto:bob@example.org> .
"""

class Person(RDFModel, select=OfType(FOAF.Person)):
    iri: Id
    name: str = Prop(FOAF.name, lang=Lang.prefer("en"))
    emails: list[str] = Prop(FOAF.mbox)

graph = Graph()
graph.parse(data=data, format="turtle")
people = Person.project(graph)  # list[Person]
```

See [documentation](https://vlizbe.github.io/semantic-sugar/) for details.

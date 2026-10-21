# `semantic-sugar`: projecting RDF graphs onto Pydantic models and back

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
See [documentation](https://vlizbe.github.io/semantic-sugar/) for details.

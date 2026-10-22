from __future__ import annotations

from rdflib import URIRef
from rdflib.namespace import OWL

from semantic_sugar import Id, OfType, Prop, RDFModel
from semantic_sugar.ontologies.rdfs import RDFSClass


class OWLClass(RDFSClass, select=OfType(OWL.Class)):
    uri: Id


class OWLOntology(RDFSClass, select=OfType(OWL.Ontology)):
    uri: Id
    version_iri: URIRef | None = Prop(
        OWL.versionIRI, on_many="error", default=None
    )
    version_info: str | None = Prop(
        OWL.versionInfo, on_many="first", default=None
    )

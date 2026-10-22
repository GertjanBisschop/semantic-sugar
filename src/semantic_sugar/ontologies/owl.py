from __future__ import annotations

from rdflib import URIRef
from rdflib.namespace import OWL, RDFS

from semantic_sugar import Id, OfType, Prop, rdfs_defined_by
from semantic_sugar.ontologies.rdfs import RDFSClass


@rdfs_defined_by(
    ontology_iri=str(OWL),
    ontology_version_iri=str(OWL),
)
class OWLClass(RDFSClass, select=OfType(OWL.Class)): ...


@rdfs_defined_by(
    ontology_iri=str(OWL),
    ontology_version_iri=str(OWL),
)
class OWLOntology(RDFSClass, select=OfType(OWL.Ontology)):
    version_iri: URIRef | None = Prop(
        OWL.versionIRI, on_many="error", default=None
    )
    version_info: str | None = Prop(
        OWL.versionInfo, on_many="first", default=None
    )

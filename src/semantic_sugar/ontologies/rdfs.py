from __future__ import annotations

from rdflib.namespace import RDFS

from semantic_sugar import Id, OfType, Prop, RDFModel, rdfs_defined_by


@rdfs_defined_by(
    ontology_iri=str(RDFS),
    ontology_version_iri=str(RDFS),
)
class RDFSClass(RDFModel, select=OfType(RDFS.Class)):
    uri: Id
    label: str | None = Prop(RDFS.label, on_many="first", default=None)


@rdfs_defined_by(
    ontology_iri=str(RDFS),
    ontology_version_iri=str(RDFS),
)
class RDFSResource(RDFSClass, select=OfType(RDFS.Resource)): ...

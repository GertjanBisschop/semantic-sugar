from __future__ import annotations

from rdflib import DCTERMS, Namespace, URIRef

from semantic_sugar import Id, OfType, Prop, rdfs_defined_by
from semantic_sugar.ontologies.owl import OWLClass

DCAT = Namespace("http://www.w3.org/ns/dcat#")

# DCAT 3.0 version IRI
_DCAT_VERSION = "https://www.w3.org/ns/dcat-2024-08-31"


@rdfs_defined_by(
    ontology_iri=str(DCAT),
    ontology_version_iri=_DCAT_VERSION,
)
class DataService(OWLClass, select=OfType(DCAT.DataService)):
    """A data service that provides access to datasets."""

    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    endpoint_url: URIRef | None = Prop(
        DCAT.endpointURL, on_many="error", default=None
    )
    endpoint_description: URIRef | None = Prop(
        DCAT.endpointDescription, on_many="first", default=None
    )
    conforms_to: URIRef | None = Prop(
        DCTERMS.conformsTo, on_many="first", default=None
    )


@rdfs_defined_by(
    ontology_iri=str(DCAT),
    ontology_version_iri=_DCAT_VERSION,
)
class Distribution(OWLClass, select=OfType(DCAT.Distribution)):
    """A specific representation of a dataset."""

    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    access_service: DataService | None = Prop(
        DCAT.accessService, on_many="error", deref=True, default=None
    )
    media_type: URIRef | None = Prop(
        DCAT.mediaType, on_many="first", default=None
    )
    download_url: URIRef | None = Prop(
        DCAT.downloadURL, on_many="error", default=None
    )


@rdfs_defined_by(
    ontology_iri=str(DCAT),
    ontology_version_iri=_DCAT_VERSION,
)
class Dataset(OWLClass, select=OfType(DCAT.Dataset)):
    """A collection of data published or curated by a single agent."""

    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    distributions: tuple[Distribution, ...] = Prop(
        DCAT.distribution, deref=True, default_factory=tuple
    )


@rdfs_defined_by(
    ontology_iri=str(DCAT),
    ontology_version_iri=_DCAT_VERSION,
)
class Catalog(OWLClass, select=OfType(DCAT.Catalog)):
    """A curated collection of metadata about resources."""

    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    datasets: tuple[Dataset, ...] = Prop(
        DCAT.dataset, deref=True, default_factory=tuple
    )

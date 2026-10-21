from __future__ import annotations

from rdflib import DCTERMS, Namespace, URIRef

from semantic_sugar import Id, OfType, Prop, RDFModel


DCAT = Namespace("http://www.w3.org/ns/dcat#")


class DataService(RDFModel, select=OfType(DCAT.DataService)):
    """A data service that provides access to datasets."""

    uri: Id
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


class Distribution(RDFModel, select=OfType(DCAT.Distribution)):
    """A specific representation of a dataset."""

    uri: Id
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


class Dataset(RDFModel, select=OfType(DCAT.Dataset)):
    """A collection of data published or curated by a single agent."""

    uri: Id
    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    distributions: tuple[Distribution, ...] = Prop(
        DCAT.distribution, deref=True, default_factory=tuple
    )


class Catalog(RDFModel, select=OfType(DCAT.Catalog)):
    """A curated collection of metadata about resources."""

    uri: Id
    title: str | None = Prop(DCTERMS.title, on_many="first", default=None)
    description: str | None = Prop(
        DCTERMS.description, on_many="first", default=None
    )
    datasets: tuple[Dataset, ...] = Prop(
        DCAT.dataset, deref=True, default_factory=tuple
    )

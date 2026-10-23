"""Tests for the @rdfs_defined_by decorator that marks models with ontology provenance.

Verifies that:
1. The decorator sets __rdf_rdfs_defined_by__, __rdf_ontology_iri__, and
   __rdf_ontology_version_iri__ class attributes.
2. The class methods defined_by_ontology(), ontology_iri(), and
   ontology_version_iri() return the correct values.
3. to_rdf() emits rdfs:isDefinedBy triples from decorated models.
4. The ontology models (RDFS, OWL, DCAT) are properly decorated.
5. The decorator raises ValueError when called without arguments.
"""

from __future__ import annotations

from rdflib import Namespace, OWL, RDFS, URIRef

from semantic_sugar import (
    Id,
    OfType,
    Prop,
    RDFModel,
    rdfs_defined_by,
    to_rdf,
)
from semantic_sugar.ontologies.dcat import (
    Catalog,
    Dataset,
    DataService,
    Distribution,
)
from semantic_sugar.ontologies.owl import OWLClass, OWLOntology
from semantic_sugar.ontologies.rdfs import RDFSClass, RDFSResource

EX = Namespace("http://example.org/")
RDFS_ONT = "http://www.w3.org/2000/01/rdf-schema#"
OWL_ONT = "http://www.w3.org/2002/07/owl#"
DCAT_ONT = "http://www.w3.org/ns/dcat#"
DCAT_VERSION = "https://www.w3.org/ns/dcat-2024-08-31"


# --------------------------------------------------------------------------- fixture


class _Person(RDFModel, select=OfType(EX.Person)):
    """Ad-hoc model for decorator tests."""

    uri: Id
    name: str | None = Prop(RDFS.label, on_many="first", default=None)


@rdfs_defined_by(
    ontology_iri=EX.MyOntology,
    ontology_version_iri=EX.MyOntology_v1,
)
class PersonDecorated(RDFModel, select=OfType(EX.Person)):
    uri: Id
    name: str | None = Prop(RDFS.label, on_many="first", default=None)


@rdfs_defined_by(ontology_iri=EX.MyOntology)
class PersonOnlyIri(RDFModel, select=OfType(EX.Person)):
    uri: Id


@rdfs_defined_by(ontology_version_iri=EX.MyOntology_v1)
class PersonOnlyVersion(RDFModel, select=OfType(EX.Person)):
    uri: Id


# --------------------------------------------------------------------------- tests


class TestDecoratorAttributes:
    """Verify the decorator sets the expected class-level attributes."""

    def test_undecorated_has_no_metadata(self) -> None:
        """Models without @rdfs_defined_by have None metadata."""
        assert _Person.defined_by_ontology() is None
        assert _Person.ontology_iri() is None
        assert _Person.ontology_version_iri() is None

    def test_decorated_sets_all_attributes(self) -> None:
        """@rdfs_defined_by with both IRIs sets all three attributes."""
        assert PersonDecorated.defined_by_ontology() == EX.MyOntology_v1
        assert PersonDecorated.ontology_iri() == EX.MyOntology
        assert PersonDecorated.ontology_version_iri() == EX.MyOntology_v1

    def test_only_ontology_iri(self) -> None:
        """When only ontology_iri is given, rdfs_defined_by points to it."""
        assert PersonOnlyIri.defined_by_ontology() == EX.MyOntology
        assert PersonOnlyIri.ontology_iri() == EX.MyOntology
        assert PersonOnlyIri.ontology_version_iri() is None

    def test_only_version_iri(self) -> None:
        """When only ontology_version_iri is given, rdfs_defined_by points to it."""
        assert PersonOnlyVersion.defined_by_ontology() == EX.MyOntology_v1
        assert PersonOnlyVersion.ontology_iri() is None
        assert PersonOnlyVersion.ontology_version_iri() == EX.MyOntology_v1

    def test_decorator_requires_at_least_one_arg(self) -> None:
        """Calling @rdfs_defined_by() with no arguments raises ValueError."""
        from pytest import raises

        with raises(ValueError, match="requires at least one"):

            @rdfs_defined_by()
            class Bad(RDFModel):
                uri: Id


class TestToRdfEmitsMetadata:
    """Verify to_rdf() emits rdfs:isDefinedBy triples for decorated models."""

    def test_to_rdf_emits_is_rdfs_defined_by(self) -> None:
        """Serializing a decorated instance adds rdfs:isDefinedBy."""
        person = PersonDecorated(uri=EX.Alice, name="Alice")
        g = person.to_rdf()

        # Should have rdfs:isDefinedBy pointing to the version IRI
        rdfs_defined_by_targets = list(g.objects(EX.Alice, RDFS.isDefinedBy))
        assert len(rdfs_defined_by_targets) == 1
        assert rdfs_defined_by_targets[0] == EX.MyOntology_v1

    def test_to_rdf_emits_ontology_version_iri(self) -> None:
        """The ontology node gets owl:versionIRI triple."""
        person = PersonDecorated(uri=EX.Alice, name="Alice")
        g = person.to_rdf()

        version_triples = list(g.objects(EX.MyOntology_v1, OWL.versionIRI))
        assert len(version_triples) >= 1

    def test_to_rdf_undecorated_no_metadata(self) -> None:
        """Serializing an undecorated instance has no rdfs:isDefinedBy."""
        person = _Person(uri=EX.Bob, name="Bob")
        g = person.to_rdf()

        rdfs_defined_by_targets = list(g.objects(EX.Bob, RDFS.isDefinedBy))
        assert len(rdfs_defined_by_targets) == 0

    def test_to_rdf_only_ontology_iri(self) -> None:
        """When only ontology_iri is set, rdfs_defined_by points to it."""
        person = PersonOnlyIri(uri=EX.Charlie)
        g = person.to_rdf()

        rdfs_defined_by_targets = list(g.objects(EX.Charlie, RDFS.isDefinedBy))
        assert len(rdfs_defined_by_targets) == 1
        assert rdfs_defined_by_targets[0] == EX.MyOntology

    def test_to_rdf_preserves_other_triples(self) -> None:
        """rdfs:isDefinedBy is added alongside normal field triples."""
        person = PersonDecorated(uri=EX.Alice, name="Alice")
        g = person.to_rdf()

        # Should have the label
        labels = list(g.objects(EX.Alice, RDFS.label))
        assert len(labels) == 1
        assert str(labels[0]) == "Alice"

        # Should have rdf:type
        types = list(
            g.objects(
                EX.Alice,
                URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
            )
        )
        assert EX.Person in types

        # Should have rdfs:isDefinedBy
        rdfs_defined_by_targets = list(g.objects(EX.Alice, RDFS.isDefinedBy))
        assert len(rdfs_defined_by_targets) == 1


class TestOntologyModelsDecorated:
    """Verify the bundled ontology models are decorated with correct IRIs."""

    def test_rdfs_class_rdfs_defined_by(self) -> None:
        assert RDFSClass.defined_by_ontology() == URIRef(RDFS_ONT)
        assert RDFSClass.ontology_iri() == URIRef(RDFS_ONT)

    def test_rdfs_resource_rdfs_defined_by(self) -> None:
        assert RDFSResource.defined_by_ontology() == URIRef(RDFS_ONT)

    def test_owl_class_rdfs_defined_by(self) -> None:
        assert OWLClass.defined_by_ontology() == URIRef(OWL_ONT)
        assert OWLClass.ontology_iri() == URIRef(OWL_ONT)

    def test_owl_ontology_rdfs_defined_by(self) -> None:
        assert OWLOntology.defined_by_ontology() == URIRef(OWL_ONT)

    def test_dcat_dataset_rdfs_defined_by(self) -> None:
        assert Dataset.defined_by_ontology() == URIRef(DCAT_VERSION)
        assert Dataset.ontology_iri() == URIRef(DCAT_ONT)

    def test_dcat_catalog_rdfs_defined_by(self) -> None:
        assert Catalog.defined_by_ontology() == URIRef(DCAT_VERSION)

    def test_dcat_distribution_rdfs_defined_by(self) -> None:
        assert Distribution.ontology_iri() == URIRef(DCAT_ONT)

    def test_dcat_data_service_rdfs_defined_by(self) -> None:
        assert DataService.ontology_version_iri() == URIRef(DCAT_VERSION)

    def test_ontology_model_to_rdf_emits_is_rdfs_defined_by(self) -> None:
        """Serializing an ontology model emits rdfs:isDefinedBy."""
        dataset = Dataset(uri=EX.MyDataset, title="My Dataset")
        g = dataset.to_rdf()

        rdfs_defined_by_targets = list(
            g.objects(EX.MyDataset, RDFS.isDefinedBy)
        )
        assert len(rdfs_defined_by_targets) == 1
        assert rdfs_defined_by_targets[0] == URIRef(DCAT_VERSION)

    def test_owl_class_to_rdf_emits_is_rdfs_defined_by(self) -> None:
        """Serializing an OWLClass emits rdfs:isDefinedBy to OWL ontology."""
        owl_cls = OWLClass(uri=EX.MyClass)
        g = owl_cls.to_rdf()

        rdfs_defined_by_targets = list(g.objects(EX.MyClass, RDFS.isDefinedBy))
        assert len(rdfs_defined_by_targets) == 1
        assert rdfs_defined_by_targets[0] == URIRef(OWL_ONT)

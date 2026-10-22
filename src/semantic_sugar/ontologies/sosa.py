from __future__ import annotations

from rdflib import Namespace, URIRef

from semantic_sugar import OfType, rdfs_defined_by, Prop
from semantic_sugar.ontologies.owl import OWLClass

SOSA = Namespace("http://www.w3.org/ns/sosa/")
SOSA_2023 = "http://www.w3.org/ns/sosa/2023/"
SSN = Namespace("http://www.w3.org/ns/ssn/")
QUDT = Namespace("http://qudt.org/schema/qudt/")


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class FeatureOfInterest(OWLClass, select=OfType(SOSA.FeatureOfInterest)):
    """An entity or phenomenon that is the target of an observation or actuation."""

    has_property: tuple["Property", ...] = Prop(
        SSN.hasProperty, deref=True, default_factory=tuple
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class Property(OWLClass, select=OfType(SOSA.Property)):
    """A characteristic of a feature of interest that can be observed or acted upon."""

    is_property_of: tuple["FeatureOfInterest", ...] | None = Prop(
        SSN.isPropertyOf, deref=True, default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class Asset(OWLClass, select=OfType(SOSA.Asset)):
    """A physical entity that can be deployed or hosted."""

    is_hosted_by: Platform | None = Prop(
        SOSA.isHostedBy, deref=True, on_many="error", default=None
    )
    has_deployment: Deployment | None = Prop(
        SSN.hasDeployment, deref=True, on_many="error", default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class Platform(Asset, select=OfType(SOSA.Platform)):
    """A physical or virtual entity that carries one or more systems."""

    hosts: tuple[System, ...] | None = Prop(
        SOSA.hosts, deref=True, default=None
    )
    in_deployment: Deployment | None = Prop(
        SSN.inDeployment, deref=True, on_many="error", default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class System(Asset, select=OfType(SOSA.System)):
    """A device or arrangement of devices capable of acting, detecting, or generating stimuli."""

    for_property: tuple[Property, ...] | None = Prop(
        SSN.forProperty, deref=True, default=None
    )
    has_subsystem: tuple[System, ...] | None = Prop(
        SSN.hasSubSystem, deref=True, default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class Sensor(System, select=OfType(SOSA.Sensor)):
    """A device that derives or calculates measurements of a property of interest."""

    observes: tuple[Property, ...] | None = Prop(
        SOSA.observes, deref=True, default=None
    )
    made_observation: tuple[Observation, ...] | None = Prop(
        SOSA.madeObservation, deref=True, default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class Deployment(OWLClass, select=OfType(SSN.Deployment)):
    """The arrangement of a system or platform for a specific purpose."""

    deployed_on_platform: Platform = Prop(
        SSN.deployedOnPlatform, deref=True, on_many="error"
    )
    deployed_system: tuple[System, ...] | None = Prop(
        SSN.deployedSystem, deref=True, default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class Observation(OWLClass, select=OfType(SOSA.Observation)):
    """The act of being able to derive or calculate measurements of a property of interest."""

    made_by_sensor: Sensor = Prop(
        SOSA.madeBySensor, deref=True, on_many="error"
    )
    has_feature_of_interest: FeatureOfInterest | None = Prop(
        SOSA.hasFeatureOfInterest, deref=True, on_many="error", default=None
    )
    observed_property: Property = Prop(
        SOSA.observedProperty, deref=True, on_many="error"
    )
    has_result: URIRef | None = Prop(
        SOSA.hasResult, on_many="error", default=None
    )
    has_simple_result: str | None = Prop(
        SOSA.hasSimpleResult, on_many="first", default=None
    )
    result_time: str | None = Prop(
        SOSA.resultTime, on_many="first", default=None
    )
    phenomenon_time: str | None = Prop(
        SOSA.phenomenonTime, on_many="first", default=None
    )
    used_procedure: URIRef | None = Prop(
        SOSA.usedProcedure, on_many="first", default=None
    )


@rdfs_defined_by(
    ontology_iri=str(SOSA),
    ontology_version_iri=SOSA_2023,
)
class ObservationCollection(
    OWLClass, select=OfType(SOSA.ObservationCollection)
):
    """A container for a set of data derived from observations."""

    made_by_sensor: tuple[Sensor, ...] = Prop(
        SOSA.madeBySensor, deref=True, default_factory=tuple
    )
    has_feature_of_interest: tuple[FeatureOfInterest, ...] | None = Prop(
        SOSA.hasFeatureOfInterest, deref=True, default=None
    )
    observed_property: tuple[Property, ...] = Prop(
        SOSA.observedProperty, deref=True, default_factory=tuple
    )
    has_member: tuple[Observation, ...] = Prop(
        SOSA.hasMember, deref=True, default_factory=tuple
    )

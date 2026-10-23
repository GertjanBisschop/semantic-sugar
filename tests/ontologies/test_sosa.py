"""SOSA round-trip tests based on simple-closure.ttl.

Builds SOSA models as Pydantic instances, serializes to RDF, projects back,
and compares — mirroring the structure in simple-closure.ttl (properties,
sensors, and a system with subsystems).
"""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import SKOS

from semantic_sugar.ontologies.sosa import (
    Property,
    Sensor,
    System,
    OfType,
    Prop,
)


EX = Namespace("https://example.org/data/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SSN = Namespace("http://www.w3.org/ns/ssn/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
SKOS


class PropertyExtension(Property, select=OfType(SOSA.Property)):
    skos_broader: URIRef | None = Prop(
        SKOS.broader, on_many="first", default=None
    )
    unit: URIRef | None = Prop(QUDT.hasUnit, on_many="first", default=None)


class TestSosaRoundTrip:
    """Build SOSA models, serialize to RDF, project back, and compare."""

    def _build_station(self) -> System:
        """Construct a weather station matching simple-closure.ttl."""
        temp_prop = Property(
            uri=EX.Temperature,
            label="A temperature property",
        )

        press_prop = Property(
            uri=EX.Pressure,
            label="A pressure property",
        )

        temp_sensor = Sensor(
            uri=EX.sens_temp,
            label="Specific temperature sensor",
            observes=(temp_prop,),
        )

        press_sensor = Sensor(
            uri=EX.sens_press,
            label="Specific pressure sensor",
            observes=(press_prop,),
        )

        station = System(
            uri=EX.WeatherStation,
            label="The weather station",
            has_subsystem=(temp_sensor, press_sensor),
        )
        return station

    def test_pydantic_to_rdf(self) -> None:
        """Pydantic instances serialize to an RDF graph with the expected triples."""
        station = self._build_station()
        g = station.to_rdf()

        # System type and label
        assert (EX.WeatherStation, RDF.type, SOSA.System) in g
        assert (
            EX.WeatherStation,
            RDF.value,
            Literal("The weather station"),
        ) in g or (
            EX.WeatherStation,
            URIRef("http://www.w3.org/2000/01/rdf-schema#label"),
            Literal("The weather station"),
        ) in g

        # Sensors
        assert (EX.sens_temp, RDF.type, SOSA.Sensor) in g
        assert (EX.sens_press, RDF.type, SOSA.Sensor) in g

        # Subsystem relationships
        assert (EX.WeatherStation, SSN.hasSubSystem, EX.sens_temp) in g
        assert (EX.WeatherStation, SSN.hasSubSystem, EX.sens_press) in g

        # Observed properties
        assert (EX.sens_temp, SOSA.observes, EX.Temperature) in g
        assert (EX.sens_press, SOSA.observes, EX.Pressure) in g

        # Properties
        assert (EX.Temperature, RDF.type, SOSA.Property) in g
        assert (EX.Pressure, RDF.type, SOSA.Property) in g

    def test_rdf_to_pydantic(self) -> None:
        """RDF graph produced by to_rdf can be projected back to Pydantic models."""
        station = self._build_station()
        g = station.to_rdf()

        # Project the system back
        systems = System.project(g, select=[EX.WeatherStation])
        assert len(systems) == 1
        round_trip = systems[0]

        assert round_trip.uri == EX.WeatherStation
        assert round_trip.label == "The weather station"
        assert len(round_trip.has_subsystem or []) == 2

        # Check sensors are dereferenced
        subsystem_uris = {s.uri for s in round_trip.has_subsystem or []}
        assert EX.sens_temp in subsystem_uris
        assert EX.sens_press in subsystem_uris

        # Project sensors separately to check observed properties
        sensors = Sensor.project(g)
        assert len(sensors) == 2
        temp_sensor = next(s for s in sensors if s.uri == EX.sens_temp)
        assert temp_sensor.observes is not None
        assert any(p.uri == EX.Temperature for p in temp_sensor.observes)

    def test_full_round_trip_equality(self) -> None:
        """Pydantic → RDF → Pydantic preserves all scalar field values."""
        original = self._build_station()
        g = original.to_rdf()
        round_trip = System.project(g, select=[original.uri])[0]

        assert round_trip.uri == original.uri
        assert round_trip.label == original.label

        # Subsystems order is non-deterministic
        orig_subs = {s.uri: s for s in original.has_subsystem or []}
        rt_subs = {s.uri: s for s in round_trip.has_subsystem or []}

        for uri, orig_sub in orig_subs.items():
            rt_sub = rt_subs[uri]
            assert rt_sub.uri == orig_sub.uri
            assert rt_sub.label == orig_sub.label

    def test_select_by_type(self) -> None:
        """OfType selector finds all nodes of a given SOSA type."""
        station = self._build_station()
        g = station.to_rdf()

        sensors = Sensor.project(g)
        assert len(sensors) == 2

        properties = Property.project(g)
        assert len(properties) == 2
        prop_uris = {p.uri for p in properties}
        assert EX.Temperature in prop_uris
        assert EX.Pressure in prop_uris

    def test_load_ttl_and_project(self) -> None:
        """Load simple-closure.ttl, project models, serialize back, and re-project.

        Note: simple-closure.ttl defines sensors as instances of OWL subclasses
        (sensor:TemperatureSensor, sensor:PressureSensor), not direct sosa:Sensor
        or sosa:System instances.  OfType matches exact rdf:type only, so only
        the weather station (a sosa:System) is projected.  The two sensors are
        not found via System.project without OWL reasoning.
        """
        from pathlib import Path

        ttl_path = Path(__file__).parent / "input" / "simple-closure.ttl"
        content = ttl_path.read_text()

        g = Graph()
        g.parse(data=content, format="turtle")

        # Only the weather station has rdf:type sosa:System in the TTL file
        systems = System.project(g)
        assert len(systems) == 1
        assert systems[0].uri == EX.WeatherStation

        # Serialize back to RDF
        g2 = Graph()
        for sys in systems:
            sys.to_rdf(g2)

        # Re-project from the serialized graph
        systems2 = System.project(g2, select=[s.uri for s in systems])
        assert len(systems2) == len(systems)

        for orig, rt in zip(systems, systems2):
            assert rt.uri == orig.uri
            if orig.label is not None:
                assert rt.label == orig.label

    def test_extension(self):
        pass

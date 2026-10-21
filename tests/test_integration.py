"""Integration tests projecting SOSA 2023 sensor data from simple-closure.ttl.

Tests the full model hierarchy:
  ObservedPropertyContext → SensorContext → WeatherStation
using Prop(), Sparql derivations, and deref=True for nested models.

The SOSA 2023 edition adds terms like sosa:System and sosa:hasSubSystem that are
not in rdflib's built-in SOSA namespace, so they are defined as URIRef constants.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import FOAF, Graph, Namespace, OWL, RDF, RDFS, URIRef
from rdflib import SOSA, SKOS  # built-in rdflib namespaces

from semantic_sugar import Id, OfType, Prop, RDFModel, Sparql

# --------------------------------------------------------------------------- namespaces

EX     = Namespace("https://example.org/data/")
SENSOR = Namespace("https://example.org/sensor/")
QK     = Namespace("http://qudt.org/vocab/quantitykind/")
QUDT   = Namespace("http://qudt.org/schema/qudt/")
UNIT   = Namespace("http://qudt.org/vocab/unit/")

# SOSA 2023 terms not in rdflib's built-in SOSA namespace
SOSA_2023 = Namespace("http://www.w3.org/ns/sosa/")
SOSA_System       = URIRef(str(SOSA_2023.System))
SOSA_hasSubSystem = URIRef(str(SOSA_2023.hasSubSystem))


# --------------------------------------------------------------------------- fixture

@pytest.fixture
def g() -> Graph:
    """Load the simple-closure.ttl graph."""
    graph = Graph()
    ttl_path = Path(__file__).parent / "input" / "simple-closure.ttl"
    graph.parse(str(ttl_path), format="turtle")
    return graph


# --------------------------------------------------------------------------- models

class ObservedPropertyContext(RDFModel):
    """A SOSA observable property with its quantity kind and unit."""

    uri: Id
    label: str | None = Prop(RDFS.label, on_many="first", default=None)
    quantity_kind: str | None = Prop(SKOS.broader, on_many="first", default=None)
    unit: str | None = Prop(QUDT.hasUnit, on_many="first", default=None)


class SensorContext(RDFModel):
    """A SOSA sensor with its observed properties resolved via OWL restrictions."""

    uri: Id
    label: str | None = Prop(RDFS.label, on_many="first", default=None)
    observed_properties: tuple[ObservedPropertyContext, ...] = Prop(
        Sparql(
            """
            SELECT ?v WHERE {
                ?this a ?sensorClass .
                ?sensorClass rdfs:subClassOf [
                    a owl:Restriction ;
                    owl:onProperty sosa:observes ;
                    owl:hasValue ?v
                ] .
            }
            """,
            init_ns={"sosa": SOSA, "owl": OWL, "rdfs": RDFS}
        ),
        deref=True
    )


class WeatherStation(RDFModel):
    """A weather station composed of sensor sub-systems (SOSA 2023)."""

    uri: Id
    label: str | None = Prop(RDFS.label, on_many="first", default=None)
    sub_systems: tuple[SensorContext, ...] = Prop(SOSA_hasSubSystem, deref=True)


# --------------------------------------------------------------------------- tests

class TestObservedPropertyContext:
    """Project individual observed properties from the graph."""

    def test_temperature_projected(self, g: Graph) -> None:
        props = ObservedPropertyContext.project(g, select=[EX.Temperature])
        assert len(props) == 1
        p = props[0]
        assert p.uri == EX.Temperature
        assert p.label == "A temperature property"
        assert p.quantity_kind == str(QK.Temperature)
        assert p.unit == str(UNIT.K)

    def test_pressure_projected(self, g: Graph) -> None:
        props = ObservedPropertyContext.project(g, select=[EX.Pressure])
        assert len(props) == 1
        p = props[0]
        assert p.uri == EX.Pressure
        assert p.label == "A pressure property"
        assert p.quantity_kind == str(QK.Pressure)
        assert p.unit == str(UNIT.PA)

    def test_both_properties_together(self, g: Graph) -> None:
        props = ObservedPropertyContext.project(g, select=[EX.Temperature, EX.Pressure])
        assert len(props) == 2
        uris = {p.uri for p in props}
        assert EX.Temperature in uris
        assert EX.Pressure in uris


class TestSensorContext:
    """Project sensors and verify OWL restriction-based observed_properties."""

    def test_temperature_sensor_observed_properties(self, g: Graph) -> None:
        sensors = SensorContext.project(g, select=[EX.sens_temp])
        assert len(sensors) == 1
        s = sensors[0]
        assert s.uri == EX.sens_temp
        assert s.label == "Specific temperature sensor"
        assert len(s.observed_properties) == 1
        assert s.observed_properties[0].uri == EX.Temperature

    def test_pressure_sensor_observed_properties(self, g: Graph) -> None:
        sensors = SensorContext.project(g, select=[EX.sens_press])
        assert len(sensors) == 1
        s = sensors[0]
        assert s.uri == EX.sens_press
        assert s.label == "Specific pressure sensor"
        assert len(s.observed_properties) == 1
        assert s.observed_properties[0].uri == EX.Pressure

    def test_both_sensors_together(self, g: Graph) -> None:
        sensors = SensorContext.project(g, select=[EX.sens_temp, EX.sens_press])
        assert len(sensors) == 2
        uris = {s.uri for s in sensors}
        assert EX.sens_temp in uris
        assert EX.sens_press in uris

    def test_sensor_observed_property_details(self, g: Graph) -> None:
        """Verify nested ObservedPropertyContext carries full details."""
        sensors = SensorContext.project(g, select=[EX.sens_temp])
        s = sensors[0]
        op = s.observed_properties[0]
        assert op.label == "A temperature property"
        assert op.quantity_kind == str(QK.Temperature)
        assert op.unit == str(UNIT.K)

    def test_sensors_via_of_type_infer(self, g: Graph) -> None:
        """OfType with infer=True finds sensors through subclass hierarchy."""
        sensors = SensorContext.project(g, select=OfType(SOSA.Sensor, infer=True))
        assert len(sensors) == 2
        uris = {s.uri for s in sensors}
        assert EX.sens_temp in uris
        assert EX.sens_press in uris


class TestWeatherStation:
    """Project the weather station with nested sensor sub-systems (SOSA 2023)."""

    def test_weather_station_label(self, g: Graph) -> None:
        stations = WeatherStation.project(g, select=[EX.WeatherStation])
        assert len(stations) == 1
        ws = stations[0]
        assert ws.uri == EX.WeatherStation
        assert ws.label == "The weather station"

    def test_weather_station_sub_systems_count(self, g: Graph) -> None:
        stations = WeatherStation.project(g, select=[EX.WeatherStation])
        ws = stations[0]
        assert len(ws.sub_systems) == 2

    def test_weather_station_sub_systems_detail(self, g: Graph) -> None:
        """Verify the full nesting: station → sensors → observed properties."""
        stations = WeatherStation.project(g, select=[EX.WeatherStation])
        ws = stations[0]
        sub_uris = {s.uri for s in ws.sub_systems}
        assert EX.sens_temp in sub_uris
        assert EX.sens_press in sub_uris

        # Find each sensor and check its observed properties
        for sensor in ws.sub_systems:
            assert len(sensor.observed_properties) == 1
            op = sensor.observed_properties[0]
            assert op.label is not None
            assert op.quantity_kind is not None
            assert op.unit is not None

    def test_weather_station_via_of_type(self, g: Graph) -> None:
        """Select the weather station using OfType with SOSA 2023 System."""
        stations = WeatherStation.project(g, select=OfType(SOSA_System))
        assert len(stations) == 1
        assert stations[0].uri == EX.WeatherStation
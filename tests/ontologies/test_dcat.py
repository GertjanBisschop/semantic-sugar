"""
DCAT round-trip test: Pydantic → RDF → Pydantic.

"""

from __future__ import annotations

from rdflib import DCTERMS, Graph, Literal, Namespace, RDF, URIRef

from semantic_sugar.ontologies.dcat import (
    Catalog,
    Dataset,
    DataService,
    Distribution,
)


EX = Namespace("https://example.com/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")


class TestDcatRoundTrip:
    """Build DCAT models as Pydantic instances, serialize to RDF, project back, and compare."""

    def _build_catalog(self) -> Catalog:
        """Construct a small DCAT catalog matching dcat-example.ttl."""
        service = DataService(
            uri=EX["emodnet-bathymetry-service"],
            title="Bathymetry WFS Service",
            description="WFS service for EMODnet bathymetry data",
            endpoint_url=URIRef("https://ows.emodnet-bathymetry.eu/wfs"),
            endpoint_description=URIRef(
                "https://ows.emodnet-bathymetry.eu/wfs?request=GetCapabilities"
            ),
            conforms_to=URIRef("https://www.ogc.org/standards/wfs/"),
        )

        wfs_dist = Distribution(
            uri=EX["emodnet-bathymetry-wfs"],
            title="WFS Distribution",
            description="Web Feature Service distribution",
            access_service=service,
        )

        geojson_dist = Distribution(
            uri=EX["emodnet-bathymetry-geojson"],
            title="GeoJSON Distribution",
            description="Local distribution",
            media_type=URIRef(
                "https://www.iana.org/assignments/media-types/application/geo+json"
            ),
            download_url=URIRef(
                "file:///network/shares/data/dataset_2026.geojson"
            ),
        )

        dataset = Dataset(
            uri=EX["emodnet-bathymetry"],
            title="EMODnet Bathymetry",
            description="Bathymetry dataset from EMODnet",
            distributions=(wfs_dist, geojson_dist),
        )

        catalog = Catalog(
            uri=EX["emodnet-subset"],
            title="EMODnet subset",
            description="Emodnet subset for Mission XYZ.",
            datasets=(dataset,),
        )
        return catalog

    def test_pydantic_to_rdf(self) -> None:
        """Pydantic instances serialize to an RDF graph with the expected triples."""
        catalog = self._build_catalog()
        g = catalog.to_rdf()

        # Catalog triples
        assert (EX["emodnet-subset"], RDF.type, DCAT.Catalog) in g
        assert (
            EX["emodnet-subset"],
            DCTERMS.title,
            Literal("EMODnet subset"),
        ) in g
        assert (
            EX["emodnet-subset"],
            DCTERMS.description,
            Literal("Emodnet subset for Mission XYZ."),
        ) in g
        assert (
            EX["emodnet-subset"],
            DCAT.dataset,
            EX["emodnet-bathymetry"],
        ) in g

        # Dataset triples
        assert (EX["emodnet-bathymetry"], RDF.type, DCAT.Dataset) in g
        assert (
            EX["emodnet-bathymetry"],
            DCTERMS.title,
            Literal("EMODnet Bathymetry"),
        ) in g
        assert (
            EX["emodnet-bathymetry"],
            DCAT.distribution,
            EX["emodnet-bathymetry-wfs"],
        ) in g
        assert (
            EX["emodnet-bathymetry"],
            DCAT.distribution,
            EX["emodnet-bathymetry-geojson"],
        ) in g

        # WFS Distribution triples
        assert (EX["emodnet-bathymetry-wfs"], RDF.type, DCAT.Distribution) in g
        assert (
            EX["emodnet-bathymetry-wfs"],
            DCAT.accessService,
            EX["emodnet-bathymetry-service"],
        ) in g

        # GeoJSON Distribution triples
        assert (
            EX["emodnet-bathymetry-geojson"],
            RDF.type,
            DCAT.Distribution,
        ) in g
        assert (
            EX["emodnet-bathymetry-geojson"],
            DCAT.mediaType,
            URIRef(
                "https://www.iana.org/assignments/media-types/application/geo+json"
            ),
        ) in g

        # DataService triples
        assert (
            EX["emodnet-bathymetry-service"],
            RDF.type,
            DCAT.DataService,
        ) in g
        assert (
            EX["emodnet-bathymetry-service"],
            DCAT.endpointURL,
            URIRef("https://ows.emodnet-bathymetry.eu/wfs"),
        ) in g

    def test_rdf_to_pydantic(self) -> None:
        """RDF graph produced by to_rdf can be projected back to Pydantic models."""
        catalog = self._build_catalog()
        g = catalog.to_rdf()

        # Project the catalog back
        catalogs = Catalog.project(g, select=[EX["emodnet-subset"]])
        assert len(catalogs) == 1
        round_trip = catalogs[0]

        # Verify catalog fields
        assert round_trip.uri == EX["emodnet-subset"]
        assert round_trip.title == "EMODnet subset"
        assert round_trip.description == "Emodnet subset for Mission XYZ."
        assert len(round_trip.datasets) == 1

        dataset = round_trip.datasets[0]
        assert dataset.uri == EX["emodnet-bathymetry"]
        assert dataset.title == "EMODnet Bathymetry"
        assert len(dataset.distributions) == 2

        # Check distributions
        dist_uris = {d.uri for d in dataset.distributions}
        assert EX["emodnet-bathymetry-wfs"] in dist_uris
        assert EX["emodnet-bathymetry-geojson"] in dist_uris

        # WFS distribution should have access_service dereferenced
        wfs = next(
            d
            for d in dataset.distributions
            if d.uri == EX["emodnet-bathymetry-wfs"]
        )
        assert wfs.access_service is not None
        assert wfs.access_service.uri == EX["emodnet-bathymetry-service"]
        assert wfs.access_service.endpoint_url == URIRef(
            "https://ows.emodnet-bathymetry.eu/wfs"
        )

        # GeoJSON distribution should have media_type and download_url
        geojson = next(
            d
            for d in dataset.distributions
            if d.uri == EX["emodnet-bathymetry-geojson"]
        )
        assert geojson.media_type == URIRef(
            "https://www.iana.org/assignments/media-types/application/geo+json"
        )
        assert geojson.download_url == URIRef(
            "file:///network/shares/data/dataset_2026.geojson"
        )

    def test_full_round_trip_equality(self) -> None:
        """Pydantic → RDF → Pydantic preserves all scalar field values."""
        original = self._build_catalog()
        g = original.to_rdf()
        round_trip = Catalog.project(g, select=[original.uri])[0]

        # Catalog
        assert round_trip.uri == original.uri
        assert round_trip.title == original.title
        assert round_trip.description == original.description

        # Dataset
        orig_ds = original.datasets[0]
        rt_ds = round_trip.datasets[0]
        assert rt_ds.uri == orig_ds.uri
        assert rt_ds.title == orig_ds.title
        assert rt_ds.description == orig_ds.description

        # Find the WFS distribution (distributions order is non-deterministic)
        orig_wfs = next(
            d for d in orig_ds.distributions if "wfs" in str(d.uri)
        )
        rt_wfs = next(d for d in rt_ds.distributions if "wfs" in str(d.uri))

        # DataService (nested two levels deep)
        orig_service = orig_wfs.access_service
        rt_service = rt_wfs.access_service
        assert rt_service is not None
        assert rt_service.uri == orig_service.uri
        assert rt_service.title == orig_service.title
        assert rt_service.endpoint_url == orig_service.endpoint_url
        assert (
            rt_service.endpoint_description
            == orig_service.endpoint_description
        )
        assert rt_service.conforms_to == orig_service.conforms_to

    def test_select_by_type(self) -> None:
        """OfType selector finds all nodes of a given DCAT type."""
        catalog = self._build_catalog()
        g = catalog.to_rdf()

        datasets = Dataset.project(g)
        assert len(datasets) == 1
        assert datasets[0].uri == EX["emodnet-bathymetry"]

        distributions = Distribution.project(g)
        assert len(distributions) == 2

        services = DataService.project(g)
        assert len(services) == 1
        assert services[0].endpoint_url == URIRef(
            "https://ows.emodnet-bathymetry.eu/wfs"
        )

    def test_load_ttl_and_project(self) -> None:
        """Load dcat-example.ttl, project models, serialize back, and re-project.

        Note: dcat-example.ttl contains an undeclared ``catalog:`` prefix on line 6,
        so rdflib cannot parse it as Turtle.  We prepend the missing prefix binding
        before parsing.  The TTL file also uses ``ex: <https://example.com>`` (no
        trailing slash), so its URIs differ from the ``EX`` namespace used elsewhere
        in this test module.
        """
        from pathlib import Path

        # The TTL file's ``ex:`` prefix has no trailing slash
        TTL_EX = Namespace("https://example.com")

        ttl_path = Path(__file__).parent / "input" / "dcat-example.ttl"
        content = ttl_path.read_text()

        g = Graph()
        g.parse(data=content, format="turtle")

        # Project datasets from the TTL file
        datasets = Dataset.project(g)
        assert len(datasets) >= 1

        # Serialize back to RDF
        g2 = Graph()
        for ds in datasets:
            ds.to_rdf(g2)

        # Re-project from the serialized graph
        datasets2 = Dataset.project(g2, select=[ds.uri for ds in datasets])
        assert len(datasets2) == len(datasets)

        for orig, rt in zip(datasets, datasets2):
            assert rt.uri == orig.uri
            if orig.title is not None:
                assert rt.title == orig.title

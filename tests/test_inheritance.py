"""Tests for model inheritance: projecting OWL classes as RDFS classes.

OWLClass (select=OfType(OWL.Class)) is a subclass of RDFSClass
(select=OfType(RDFS.Class)) in the Python model hierarchy.

These tests verify that a graph containing owl:Class instances can be
projected down to the parent RDFSClass model using OfType(RDFS.Class, infer=True)
without requiring an explicit ``owl:Class rdfs:subClassOf rdfs:Class`` axiom in the
graph.  The Python model inheritance chain is enough: ``OfType`` walks the
RDFModel subclass hierarchy to discover that ``OWLClass`` extends ``RDFSClass``,
and automatically includes ``owl:Class`` as a target type when inferring.
"""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS

from semantic_sugar import OfType, RDFModel
from semantic_sugar.ontologies.owl import OWLClass
from semantic_sugar.ontologies.rdfs import RDFSClass


EX = Namespace("http://example.org/")


# --------------------------------------------------------------------------- fixture


def _build_graph() -> Graph:
    """Build a small graph with owl:Class and rdfs:Class resources.

    Note: No explicit ``owl:Class rdfs:subClassOf rdfs:Class`` axiom is added.
    The Python model inheritance (OWLClass extends RDFSClass) is sufficient for
    OfType inference to discover owl:Class instances when projecting as RDFSClass.
    """
    g = Graph()

    # An OWL class — typed as owl:Class
    g.add((EX.MyClass, RDF.type, OWL.Class))
    g.add((EX.MyClass, RDFS.label, Literal("My Class")))
    g.add((EX.MyClass, RDFS.comment, Literal("An example class")))

    # Another OWL class with a subclassOf relationship
    g.add((EX.SubClass, RDF.type, OWL.Class))
    g.add((EX.SubClass, RDFS.label, Literal("Sub Class")))
    g.add((EX.SubClass, RDFS.subClassOf, EX.MyClass))

    # A plain RDFS class (not an owl:Class)
    g.add((EX.PlainClass, RDF.type, RDFS.Class))
    g.add((EX.PlainClass, RDFS.label, Literal("Plain Class")))

    return g


# --------------------------------------------------------------------------- tests


class TestSelectorInference:
    """Verify OfType selector finds OWL classes via Python model inheritance.

    No ``owl:Class rdfs:subClassOf rdfs:Class`` triple is in the graph.
    OfType inference discovers owl:Class through the Python class hierarchy
    where OWLClass extends RDFSClass.
    """

    def test_of_type_infer_finds_all_classes(self) -> None:
        """OfType(RDFS.Class, infer=True) finds owl:Class and rdfs:Class nodes
        without the graph axiom, using Python model inheritance."""
        g = _build_graph()
        nodes = list(OfType(RDFS.Class, infer=True).select(g))
        uris = {n for n in nodes}
        assert EX.MyClass in uris
        assert EX.SubClass in uris
        assert EX.PlainClass in uris
        assert len(nodes) == 3

    def test_of_type_without_infer_finds_only_exact_rdfs_class(self) -> None:
        """OfType(RDFS.Class, infer=False) only finds exact rdfs:Class instances."""
        g = _build_graph()
        nodes = list(OfType(RDFS.Class, infer=False).select(g))
        # Only the plain rdfs:Class, not the owl:Classes
        assert len(nodes) == 1
        assert nodes[0] == EX.PlainClass

    def test_of_type_owl_class_finds_owl_instances(self) -> None:
        """OfType(OWL.Class) finds nodes typed as owl:Class."""
        g = _build_graph()
        nodes = list(OfType(OWL.Class).select(g))
        uris = {n for n in nodes}
        assert EX.MyClass in uris
        assert EX.SubClass in uris
        assert len(nodes) == 2

    def test_of_type_owl_class_excludes_plain_rdfs(self) -> None:
        """OfType(OWL.Class) does not find plain rdfs:Class instances."""
        g = _build_graph()
        nodes = list(OfType(OWL.Class).select(g))
        assert EX.PlainClass not in {n for n in nodes}


class TestProjectOWLAsRDFS:
    """Project owl:Class instances using the parent RDFSClass model.

    OfType(infer=True) discovers owl:Class via Python model inheritance,
    without requiring ``owl:Class rdfs:subClassOf rdfs:Class`` in the graph.
    """

    def test_project_owl_class_as_rdfs_class_explicit_select(self) -> None:
        """RDFSClass can project an owl:Class node when selected explicitly."""
        g = _build_graph()
        classes = RDFSClass.project(g, select=[EX.MyClass])
        assert len(classes) == 1

    def test_project_plain_rdfs_class(self) -> None:
        """RDFSClass can project a plain rdfs:Class node."""
        g = _build_graph()
        classes = RDFSClass.project(g, select=[EX.PlainClass])
        assert len(classes) == 1

    def test_project_all_classes_as_rdfs_with_infer(self) -> None:
        """RDFSClass with OfType(infer=True) finds owl:Class via Python inheritance
        without the graph axiom."""
        g = _build_graph()
        classes = RDFSClass.project(g, select=OfType(RDFS.Class, infer=True))
        # Should find all three: 2 owl:Classes + 1 rdfs:Class
        assert len(classes) == 3

    def test_project_rdfs_without_infer(self) -> None:
        """RDFSClass default selector only finds exact rdfs:Class instances."""
        g = _build_graph()
        classes = RDFSClass.project(g)
        # Only the plain rdfs:Class
        assert len(classes) == 1


class TestProjectOWLClassDirectly:
    """Project using the OWLClass model directly."""

    def test_project_owl_class_directly(self) -> None:
        """OWLClass.project finds owl:Class instances."""
        g = _build_graph()
        classes = OWLClass.project(g)
        assert len(classes) == 2

    def test_owl_class_does_not_find_plain_rdfs_class(self) -> None:
        """OWLClass only selects owl:Class, not plain rdfs:Class."""
        g = _build_graph()
        classes = OWLClass.project(g)
        assert len(classes) == 2  # only the 2 owl:Classes


class TestModelInheritance:
    """Verify Python model inheritance between OWLClass and RDFSClass."""

    def test_owl_class_is_rdfs_class(self) -> None:
        """OWLClass should be a subclass of RDFSClass in Python."""
        assert issubclass(OWLClass, RDFSClass)

    def test_projected_owl_class_is_instance_of_rdfs_class(self) -> None:
        """An OWLClass instance should also be an instance of RDFSClass."""
        g = _build_graph()
        classes = OWLClass.project(g, select=[EX.MyClass])
        assert len(classes) == 1
        assert isinstance(classes[0], OWLClass)
        assert isinstance(classes[0], RDFSClass)

    def test_rdfs_class_is_rdf_model(self) -> None:
        """RDFSClass should be a subclass of RDFModel."""
        assert issubclass(RDFSClass, RDFModel)

    def test_owl_class_is_rdf_model(self) -> None:
        """OWLClass should also be a subclass of RDFModel (transitively)."""
        assert issubclass(OWLClass, RDFModel)

    def test_selector_override(self) -> None:
        """OWLClass overrides the selector from RDFSClass."""
        # RDFSClass default selector finds only exact rdfs:Class
        g = _build_graph()
        rdfs_nodes = set(RDFSClass._nodes(g, None))
        assert EX.PlainClass in rdfs_nodes
        assert EX.MyClass not in rdfs_nodes

        # OWLClass default selector finds owl:Class instances
        owl_nodes = set(OWLClass._nodes(g, None))
        assert EX.MyClass in owl_nodes
        assert EX.SubClass in owl_nodes
        assert EX.PlainClass not in owl_nodes

    def test_parent_projection_with_owl_nodes(self) -> None:
        """RDFSClass can project nodes that are actually owl:Class instances."""
        g = _build_graph()
        # Select owl:Class nodes but project them as RDFSClass
        classes = RDFSClass.project(g, select=OfType(OWL.Class))
        assert len(classes) == 2
        # Each projected instance is an RDFSClass, not an OWLClass
        for cls in classes:
            assert isinstance(cls, RDFSClass)

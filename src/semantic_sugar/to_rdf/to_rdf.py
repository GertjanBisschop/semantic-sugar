"""Convert RDFModel instances back to an RDF graph (rdflib Graph)."""

from __future__ import annotations

from typing import Any

from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.term import Node

from semantic_sugar.models.fieldplan import FieldPlan
from semantic_sugar.models.selectors import OfType


def _get_subject(instance: Any, plan: dict[str, FieldPlan]) -> Node | None:
    """Extract the subject node from the Id field of an instance."""
    for name, fp in plan.items():
        if fp.is_id:
            value = getattr(instance, name, None)
            if value is None:
                return BNode()
            if isinstance(value, (URIRef, BNode)):
                return value
            if isinstance(value, str):
                return URIRef(value)
    return BNode()


def _get_class_types(model: type) -> list[URIRef]:
    """Extract RDF class types from the model's __rdf_select__ selector."""
    selector = getattr(model, "__rdf_select__", None)
    if isinstance(selector, OfType):
        return list(selector.classes)
    return []


def _add_literal(
    graph: Graph, subject: Node, predicate: URIRef, value: Any
) -> None:
    """Add a triple with the value converted to an appropriate RDF term."""
    # Check URIRef / BNode before str — URIRef is a subclass of str in rdflib
    if isinstance(value, (URIRef, BNode)):
        graph.add((subject, predicate, value))
    elif isinstance(value, Node):
        graph.add((subject, predicate, value))
    elif isinstance(value, bool):
        graph.add((subject, predicate, Literal(value)))
    elif isinstance(value, (int, float)):
        graph.add((subject, predicate, Literal(value)))
    elif isinstance(value, str):
        graph.add((subject, predicate, Literal(value)))
    else:
        graph.add((subject, predicate, Literal(str(value))))


def to_rdf(instance: Any, graph: Graph | None = None) -> Graph:
    """Convert an RDFModel instance to an RDF graph.

    Inspects the model's field plan to determine predicates and objectRDFModel values.
    Fields whose ``Prop`` source is a ``Sparql`` expression or a callable are
    skipped, because they have no stable predicate IRI to reverse.

    Args:
        instance: An RDFModel instance to convert.
        graph: An existing rdflib Graph to add triples to. A new empty Graph
               is created when ``None``.

    Returns:
        The graph with the instance's triples added.

    Raises:
        ValueError: If the instance has no ``Id`` field and cannot determine
                    a subject node.
    """
    if graph is None:
        graph = Graph()

    model = type(instance)
    if not getattr(model, "__rdf_projectable__", False):
        raise TypeError(f"Expected an RDFModel instance, got {model.__name__}")

    plan = model.rdf_plan()
    subject = _get_subject(instance, plan)
    if subject is None:
        raise ValueError(
            f"{model.__name__} has no Id field; cannot determine subject node"
        )

    # Add rdf:type triples from the selector
    for cls_uri in _get_class_types(model):
        graph.add((subject, RDF.type, cls_uri))

    # Process each field
    for name, fp in plan.items():
        if fp.is_id:
            continue

        # Skip fields without a reversible predicate
        if fp.spec is None:
            continue

        source = fp.spec.source
        if not isinstance(source, (URIRef,)):
            # Sparql, callable, Path — cannot reverseRDFModel
            # Path could theoretically be reversed but is complex (e.g. inverse paths)
            continue

        predicate = URIRef(source)
        value = getattr(instance, name, None)

        # Handle None / missing values
        if value is None:
            continue

        # Handle nested RDFModel instances
        if fp.model is not None:
            if fp.cardinality == "many":
                if isinstance(value, (list, tuple, set, frozenset)):
                    for nested in value:
                        if getattr(type(nested), "__rdf_projectable__", False):
                            nested_subject = _get_subject(
                                nested, nested.rdf_plan()
                            )
                            graph.add((subject, predicate, nested_subject))
                            to_rdf(nested, graph)
                continue
            else:
                # Single nested model
                if getattr(type(value), "__rdf_projectable__", False):
                    nested_subject = _get_subject(value, value.rdf_plan())
                    graph.add((subject, predicate, nested_subject))
                    to_rdf(value, graph)
                continue

        # Handle scalar values
        if fp.cardinality == "many":
            if isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    _add_literal(graph, subject, predicate, item)
            else:
                _add_literal(graph, subject, predicate, value)
        else:
            _add_literal(graph, subject, predicate, value)

    return graph


def to_rdf_many(instances: list[Any], graph: Graph | None = None) -> Graph:
    """Convert multiple RDFModel instances to a single RDF graph.

    Args:
        instances: A list of RDFModel instances.
        graph: An existing rdflib Graph to add triples to.

    Returns:
        The graph with all instances' triples added.
    """
    if graph is None:
        graph = Graph()
    for instance in instances:
        to_rdf(instance, graph)
    return graph

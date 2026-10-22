"""Stage 1 - node selection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Iterator

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.term import Node


def _get_model_subclass_types(cls: URIRef) -> list[URIRef]:
    """Walk the RDFModel Python class hierarchy to find child RDF types.

    When a model declares ``select=OfType(ChildClass)`` and inherits from a parent
    that declares ``select=OfType(ParentClass)``, and ``ParentClass == cls``, the
    child's ``ChildClass`` is returned so that ``OfType(cls, infer=True)`` can
    find instances typed as ``ChildClass`` without requiring an explicit
    ``rdfs:subClassOf`` triple in the graph.

    This bridges Python model inheritance to RDF type inference: if ``OWLClass``
    extends ``RDFSClass`` in Python, then ``OfType(RDFS.Class, infer=True)`` will
    also look for nodes typed as ``owl:Class``.
    """
    from semantic_sugar.models.rdfmodel import RDFModel

    collected: list[URIRef] = []

    # Find all models whose OfType selector includes cls
    def _find_parent_models(model: type) -> list[type]:
        parents: list[type] = []
        for sub in model.__subclasses__():
            sel = getattr(sub, "__rdf_select__", None)
            if isinstance(sel, OfType) and cls in sel.classes:
                parents.append(sub)
            # Recurse to find deeper matches
            parents.extend(_find_parent_models(sub))
        return parents

    # For each parent model, walk its subclasses to collect their OfType classes
    def _walk_children(model: type) -> None:
        for sub in model.__subclasses__():
            sel = getattr(sub, "__rdf_select__", None)
            if isinstance(sel, OfType):
                for sub_cls in sel.classes:
                    if sub_cls != cls and sub_cls not in collected:
                        collected.append(sub_cls)
            # Recurse into grandchildren
            _walk_children(sub)

    for parent in _find_parent_models(RDFModel):
        _walk_children(parent)

    return collected


def _unique(nodes: Iterable[Node]) -> list[Node]:
    return list(dict.fromkeys(nodes))


class Selector(ABC):
    """Anything that can yield the nodes to project from a graph."""

    @abstractmethod
    def select(self, graph: Graph) -> Iterator[Node]: ...

    def __and__(self, other: Any) -> "Selector":
        return AllOf(self, as_selector(other))

    def __or__(self, other: Any) -> "Selector":
        return AnyOf(self, as_selector(other))


class OfType(Selector):
    """Nodes with ``rdf:type`` in ``classes``. ``infer=True`` also follows ``rdfs:subClassOf``."""

    def __init__(self, *classes: URIRef, infer: bool = False):
        self.classes, self.infer = classes, infer

    def select(self, graph: Graph) -> Iterator[Node]:
        seen: set[Node] = set()
        for cls in self.classes:
            if self.infer:
                # Start with graph-based rdfs:subClassOf inference
                targets: list[URIRef] = list(
                    graph.transitive_subjects(RDFS.subClassOf, cls)
                )
                # Also include types discovered from Python model inheritance
                # so that OWLClass extending RDFSClass in Python makes
                # OfType(RDFS.Class, infer=True) find owl:Class instances
                # without requiring the graph to contain owl:Class rdfs:subClassOf rdfs:Class
                for model_type in _get_model_subclass_types(cls):
                    if model_type not in targets:
                        targets.append(model_type)
            else:
                targets = [cls]
            for t in targets:
                for s in graph.subjects(RDF.type, t):
                    if s not in seen:
                        seen.add(s)
                        yield s


class Sparql(Selector):
    """A SPARQL SELECT used either as a selector or as a value derivation.

    * as selector:   the query must bind ``?this``  -> the selected nodes
    * as derivation: ``?this`` is pre-bound to the current node and the query
                     must bind ``?v``                -> the derived values
    Prefixes bound on the graph are available without declaration.
    """

    def __init__(
        self,
        query: str,
        *,
        this: str = "this",
        value: str = "v",
        init_ns: dict[str, Any] | None = None,
    ):
        self.query, self.this, self.value, self.init_ns = (
            query,
            this,
            value,
            init_ns,
        )

    def select(self, graph: Graph) -> Iterator[Node]:
        for row in graph.query(self.query, initNs=self.init_ns):
            node = row.asdict().get(self.this)
            if node is not None:
                yield node

    def values(self, graph: Graph, node: Node) -> Iterator[Node]:
        for row in graph.query(
            self.query, initNs=self.init_ns, initBindings={self.this: node}
        ):
            v = row.asdict().get(self.value)
            if v is not None:
                yield v


class Nodes(Selector):
    def __init__(self, *nodes: Node | str):
        self.nodes = [n if isinstance(n, Node) else URIRef(n) for n in nodes]

    def select(self, graph: Graph) -> Iterator[Node]:
        return iter(self.nodes)


class FromCallable(Selector):
    def __init__(self, fn: Callable[[Graph], Iterable[Node]]):
        self.fn = fn

    def select(self, graph: Graph) -> Iterator[Node]:
        return iter(self.fn(graph))


class AllOf(Selector):
    def __init__(self, *parts: Selector):
        self.parts = parts

    def select(self, graph: Graph) -> Iterator[Node]:
        first, *rest = self.parts
        others = [set(p.select(graph)) for p in rest]
        return (n for n in first.select(graph) if all(n in o for o in others))


class AnyOf(Selector):
    def __init__(self, *parts: Selector):
        self.parts = parts

    def select(self, graph: Graph) -> Iterator[Node]:
        return iter(_unique(n for p in self.parts for n in p.select(graph)))


def as_selector(x: Any) -> Selector:
    if isinstance(x, Selector):
        return x
    if callable(x):
        return FromCallable(x)
    if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
        return Nodes(*x)
    raise TypeError(f"Cannot interpret {x!r} as a node selector")

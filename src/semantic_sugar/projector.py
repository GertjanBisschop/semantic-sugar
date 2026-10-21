"""Stage 3 - graph-driven projection engine."""
from __future__ import annotations

from typing import Any, Iterator

from pydantic import ValidationError
from rdflib import BNode, Graph, URIRef
from rdflib.term import Node

from .converters import Converters, default_converters
from .derive import evaluate
from .errors import CardinalityError, CycleError, ProjectionError
from .plan import MISSING, shape


class Projector:
    """Projects nodes of one graph into model instances.

    One Projector = one run: it owns the identity map and the in-progress stack.
    """

    def __init__(self, graph: Graph, *, max_depth: int | None = None,
                 identity_map: bool = True, converters: Converters = default_converters):
        self.graph, self.max_depth = graph, max_depth
        self.identity_map, self.converters = identity_map, converters
        self._done: dict[tuple[type, Node], Any] = {}
        self._active: set[tuple[type, Node]] = set()

    # ---- driver ---------------------------------------------------------
    def iter(self, model: type, nodes: list[Node],
             errors: list[ProjectionError] | None = None) -> Iterator[Any]:
        """Yield instances. With ``errors`` given, failures are collected, not raised."""
        for node in nodes:
            try:
                yield self.project_node(model, node)
            except ProjectionError as e:
                if errors is None:
                    raise
                errors.append(e)

    # ---- one node -------------------------------------------------------
    def project_node(self, model: type, node: Node, depth: int = 0) -> Any:
        key = (model, node)
        if self.identity_map and key in self._done:
            return self._done[key]
        if key in self._active:
            raise ProjectionError(node, model, None, CycleError(
                "cycle detected; break it with Prop(..., deref=False) or max_depth"))
        self._active.add(key)
        try:
            raw = self._collect(model, node, depth)
            try:
                obj = model.model_validate(raw)
            except ValidationError as ve:
                first = ve.errors()[0]["loc"] if ve.errors() else ()
                raise ProjectionError(node, model, str(first[0]) if first else None, ve) from ve
        finally:
            self._active.discard(key)
        if self.identity_map:
            self._done[key] = obj
        return obj

    def _collect(self, model: type, node: Node, depth: int) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for name, fp in model.rdf_plan().items():
            if fp.is_id:
                raw[name] = node
                continue
            try:
                values = evaluate(fp.spec, self.graph, node)
                if fp.model is not None and fp.spec.deref:
                    if self.max_depth is not None and depth >= self.max_depth:
                        items: list[Any] = []              # depth budget exhausted
                    else:
                        items = [self._nested(fp.model, v, depth + 1) for v in values]
                else:
                    items = [self.converters.convert(v) for v in values]
                shaped = shape(fp, items)
            except ProjectionError as e:
                raise e.prepend(node, name)
            except CardinalityError as e:
                raise ProjectionError(node, model, name, e) from e
            if shaped is not MISSING:
                raw[name] = shaped
        return raw

    def _nested(self, model: type, value: Node, depth: int) -> Any:
        if not isinstance(value, (URIRef, BNode)):
            raise ProjectionError(value, model, None,
                                  TypeError("expected an IRI or blank node, got a literal"))
        return self.project_node(model, value, depth)

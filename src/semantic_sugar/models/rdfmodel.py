"""The public RDFModel base class."""

from __future__ import annotations

from typing import Any, ClassVar, Iterable, Iterator

from pydantic import BaseModel, ConfigDict
from rdflib import BNode, Graph, URIRef
from rdflib.term import Node
from typing_extensions import Self

from semantic_sugar.models.errors import (
    ProjectionError,
    ProjectionResult,
    SemanticError,
)
from semantic_sugar.models.fieldplan import FieldPlan, build_plan
from semantic_sugar.models.selectors import Selector, as_selector
from semantic_sugar.from_rdf.projector import Projector
from semantic_sugar.from_rdf.rows import Projection
from semantic_sugar.to_rdf import (
    to_rdf as _to_rdf,
    to_rdf_many as _to_rdf_many,
)


class RDFModel(BaseModel):
    """Pydantic model whose fields are derived from an RDF graph.

    Class keyword:  ``class P(RDFModel, select=OfType(FOAF.Person)): ...``
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    __rdf_projectable__: ClassVar[bool] = True
    __rdf_select__: ClassVar[Selector | None] = None

    def __init_subclass__(cls, select: Any = None, **kwargs: Any) -> None:
        # class keywords reach both __init_subclass__ and __pydantic_init_subclass__
        super().__init_subclass__(**kwargs)
        if select is not None:
            cls.__rdf_select__ = as_selector(
                select
            )  # else inherited from parent
        cls.__rdf_plan__ = None

    @classmethod
    def __pydantic_init_subclass__(
        cls, select: Any = None, **kwargs: Any
    ) -> None:
        super().__pydantic_init_subclass__(**kwargs)

    @classmethod
    def rdf_plan(cls) -> dict[str, FieldPlan]:
        plan = cls.__dict__.get("__rdf_plan__")
        if plan is None:
            plan = build_plan(cls)
            cls.__rdf_plan__ = plan
        return plan

    # ---- graph-driven ----------------------------------------------------
    @classmethod
    def _nodes(cls, graph: Graph, select: Any) -> list[Node]:
        sel = as_selector(select) if select is not None else cls.__rdf_select__
        if sel is None:
            raise SemanticError(
                f"{cls.__name__} has no selector; pass select=..."
            )
        return list(dict.fromkeys(sel.select(graph)))

    @classmethod
    def iter_project(
        cls,
        graph: Graph,
        *,
        select: Any = None,
        on_error: str = "raise",
        max_depth: int | None = None,
        identity_map: bool = True,
    ) -> Iterator[Self]:
        proj = Projector(graph, max_depth=max_depth, identity_map=identity_map)
        errors: list[ProjectionError] | None = (
            [] if on_error == "skip" else None
        )
        yield from proj.iter(cls, cls._nodes(graph, select), errors)

    @classmethod
    def project(cls, graph: Graph, **opts: Any) -> list[Self]:
        """All selected nodes. ``on_error``: "raise" (default) | "skip"."""
        return list(cls.iter_project(graph, **opts))

    @classmethod
    def try_project(
        cls,
        graph: Graph,
        *,
        select: Any = None,
        max_depth: int | None = None,
        identity_map: bool = True,
    ) -> ProjectionResult[Self]:
        """Never raises per-node errors; returns objects and errors side by side."""
        result: ProjectionResult[Self] = ProjectionResult()
        proj = Projector(graph, max_depth=max_depth, identity_map=identity_map)
        result.objects = list(
            proj.iter(cls, cls._nodes(graph, select), result.errors)
        )
        return result

    @classmethod
    def project_one(
        cls, graph: Graph, node: Node | str, *, max_depth: int | None = None
    ) -> Self:
        node = node if isinstance(node, (URIRef, BNode)) else URIRef(node)
        return Projector(graph, max_depth=max_depth).project_node(cls, node)

    # ---- query-driven ----------------------------------------------------
    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Any],
        *,
        key: str | None = None,
        bind: dict[str, str] | None = None,
        on_error: str = "raise",
    ) -> list[Self]:
        rows = [r.asdict() if hasattr(r, "asdict") else dict(r) for r in rows]
        if bind is not None:
            projection = Projection.by_bind(cls, bind, key)
        else:
            names = {k for r in rows for k in r}
            projection = Projection.by_convention(cls, names)
            if key:
                projection.key = key
        return projection.from_rows(rows, on_error)

    # ---- RDF serialization -----------------------------------------------
    def to_rdf(self, graph: Graph | None = None) -> Graph:
        """Convert this instance back to an RDF graph.

        Inspects the model's field plan to determine predicates and object
        values.  Fields whose ``Prop`` source is a SPARQL expression or a
        callable are skipped because they have no stable predicate IRI.

        Args:
            graph: An existing rdflib Graph to add triples to.  A new empty
                   Graph is created when ``None``.

        Returns:
            The graph with the instance's triples added.
        """
        return _to_rdf(self, graph)

    @classmethod
    def to_rdf_many(
        cls, instances: list[Self], graph: Graph | None = None
    ) -> Graph:
        """Convert multiple instances to a single RDF graph.

        Args:
            instances: A list of model instances.
            graph: An existing rdflib Graph to add triples to.

        Returns:
            The graph with all instances' triples added.
        """
        return _to_rdf_many(instances, graph)

"""The public RDFModel base class."""

from __future__ import annotations

from typing import Any, ClassVar, Iterable, Iterator, Callable

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
    __rdf_defined_by__: ClassVar[URIRef | None] = None
    __rdf_ontology_iri__: ClassVar[URIRef | None] = None
    __rdf_ontology_version_iri__: ClassVar[URIRef | None] = None

    def __init_subclass__(
        cls,
        select: Any = None,
        defined_by: URIRef | str | None = None,
        ontology_iri: URIRef | str | None = None,
        ontology_version_iri: URIRef | str | None = None,
        **kwargs: Any,
    ) -> None:
        # class keywords reach both __init_subclass__ and __pydantic_init_subclass__
        super().__init_subclass__(**kwargs)
        if select is not None:
            cls.__rdf_select__ = as_selector(
                select
            )  # else inherited from parent
        if defined_by is not None:
            cls.__rdf_defined_by__ = (
                URIRef(defined_by)
                if isinstance(defined_by, str)
                else defined_by
            )
        if ontology_iri is not None:
            cls.__rdf_ontology_iri__ = (
                URIRef(ontology_iri)
                if isinstance(ontology_iri, str)
                else ontology_iri
            )
        if ontology_version_iri is not None:
            cls.__rdf_ontology_version_iri__ = (
                URIRef(ontology_version_iri)
                if isinstance(ontology_version_iri, str)
                else ontology_version_iri
            )
        cls.__rdf_plan__ = None

    @classmethod
    def defined_by_ontology(cls) -> URIRef | None:
        """Return the ontology IRI this model class is defined in, if any."""
        return cls.__rdf_defined_by__

    @classmethod
    def ontology_iri(cls) -> URIRef | None:
        """Return the ontology IRI (ontology:IRI), if set."""
        return cls.__rdf_ontology_iri__

    @classmethod
    def ontology_version_iri(cls) -> URIRef | None:
        """Return the ontology version IRI (ontology:versionIRI), if set."""
        return cls.__rdf_ontology_version_iri__

    @classmethod
    def __pydantic_init_subclass__(
        cls,
        select: Any = None,
        defined_by: URIRef | str | None = None,
        ontology_iri: URIRef | str | None = None,
        ontology_version_iri: URIRef | str | None = None,
        **kwargs: Any,
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


def rdfs_defined_by(
    *,
    ontology_iri: str | URIRef | None = None,
    ontology_version_iri: str | URIRef | None = None,
) -> Callable[[RDFModel], RDFModel]:
    """Mark an RDFModel subclass as defined in a specific ontology.

    When the decorated model is serialized with ``to_rdf()``, the resulting graph
    will contain ``rdfs:isDefinedBy`` pointing to the ontology version IRI
    (or ontology IRI if version is not provided), along with
    ``owl:versionIRI`` / ``owl:IRI`` triples on the ontology node.

    Args:
        ontology_iri: The stable IRI of the ontology (``owl:IRI``).
        ontology_version_iri: The version-specific IRI (``owl:versionIRI``).
                              Used as the ``rdfs:isDefinedBy`` target when set.

    Returns:
        The same class with ``defined_by``, ``ontology_iri``, and
        ``ontology_version_iri`` class keywords set.

    Raises:
        ValueError: If neither ``ontology_iri`` nor ``ontology_version_iri``
                    is provided.
    Usage::

        @defined_by(
            ontology_iri="http://www.w3.org/ns/dcat",
            ontology_version_iri="http://www.w3.org/ns/dcat-2023-12-19"
        )
        class Dataset(RDFModel, select=OfType(DCAT.Dataset)):
            uri: Id
            ...
    """
    if ontology_iri is None and ontology_version_iri is None:
        raise ValueError(
            "defined_by() requires at least one of ontology_iri or "
            "ontology_version_iri"
        )

    # rdfs:isDefinedBy points to the version IRI when available, else the base IRI
    defined_by_target: str | URIRef | None = (
        ontology_version_iri or ontology_iri
    )

    def decorator(cls: RDFModel) -> RDFModel:
        # Re-create the class with the additional class keywords.
        # __init_subclass__ will pick them up on the next subclass, but since
        # we are decorating an already-created class, we set the attributes
        # directly (mirroring what __init_subclass__ does).
        if defined_by_target is not None:
            cls.__rdf_defined_by__ = (
                URIRef(defined_by_target)
                if isinstance(defined_by_target, str)
                else defined_by_target
            )
        if ontology_iri is not None:
            cls.__rdf_ontology_iri__ = (
                URIRef(ontology_iri)
                if isinstance(ontology_iri, str)
                else ontology_iri
            )
        if ontology_version_iri is not None:
            cls.__rdf_ontology_version_iri__ = (
                URIRef(ontology_version_iri)
                if isinstance(ontology_version_iri, str)
                else ontology_version_iri
            )
        return cls

    return decorator

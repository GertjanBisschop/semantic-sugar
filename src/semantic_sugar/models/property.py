"""Stage 2 - value derivation: Prop(), Id, Lang and expression evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Callable, Iterable, Literal as Lit

from pydantic import Field
from pydantic_core import PydanticUndefined
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.paths import Path
from rdflib.term import Node

from semantic_sugar.models.selectors import Sparql
from semantic_sugar.from_rdf.converters import default_converters


# --------------------------------------------------------------------------- Id
class IdMarker:
    """Metadata marker: this field receives the node's own identifier."""

    def __repr__(self) -> str:
        return "Id"


Id = Annotated[URIRef | BNode, IdMarker()]


# ------------------------------------------------------------------------- Lang
@dataclass(frozen=True)
class Lang:
    """Language policy for literal values (non-literals always pass through)."""

    langs: tuple[str, ...]
    mode: Lit["only", "prefer"] = "only"

    @classmethod
    def only(cls, *langs: str) -> "Lang":
        return cls(tuple(l.lower() for l in langs), "only")

    @classmethod
    def prefer(cls, *langs: str) -> "Lang":
        """First language with any value wins; untagged literals are the last resort."""
        return cls(tuple(l.lower() for l in langs), "prefer")

    def apply(self, values: list[Node]) -> list[Node]:
        others = [v for v in values if not isinstance(v, Literal)]
        lits = [v for v in values if isinstance(v, Literal)]

        def with_lang(l: str) -> list[Node]:
            return [v for v in lits if (v.language or "").lower() == l]

        if self.mode == "only":
            return others + [v for l in self.langs for v in with_lang(l)]
        for l in (*self.langs, ""):
            hit = with_lang(l)
            if hit:
                return others + hit
        return others


# ------------------------------------------------------------------------- Prop
@dataclass
class PropSpec:
    source: Any  # URIRef | rdflib Path | Sparql | callable(graph, node)
    lang: Lang | None = None
    datatype: URIRef | None = None
    order_by: Any = None  # predicate or path evaluated on each value
    deref: bool = True  # False: keep nested nodes as raw URIRef/BNode
    on_many: Lit["error", "first", "last"] = (
        "error"  # scalar fields given several values
    )


def Prop(
    source: Any,
    *,
    lang: str | Lang | None = None,
    datatype: URIRef | None = None,
    order_by: Any = None,
    deref: bool = True,
    on_many: str = "error",
    default: Any = PydanticUndefined,
    default_factory: Callable | None = None,
    **field_kwargs: Any,
) -> Any:
    """Declare how a model field is derived from the graph.

    Returns a pydantic ``FieldInfo`` carrying a ``PropSpec`` in its metadata, so
    everything ``pydantic.Field`` supports (alias, description, ...) still works.
    """
    if isinstance(lang, str):
        lang = Lang.only(lang)
    spec = PropSpec(source, lang, datatype, order_by, deref, on_many)  # type: ignore[arg-type]
    kw: dict[str, Any] = dict(field_kwargs)
    if default is not PydanticUndefined:
        kw["default"] = default
    if default_factory is not None:
        kw["default_factory"] = default_factory
    info = Field(**kw)
    info.metadata.append(spec)
    return info


# ------------------------------------------------------------------- evaluation
def _sorted(values: list[Any], key: Callable[[Any], Any]) -> list[Any]:
    try:
        return sorted(values, key=key)
    except TypeError:  # heterogeneous types: fall back to text
        return sorted(values, key=lambda v: str(key(v)))


def evaluate(spec: PropSpec, graph: Graph, node: Node) -> list[Node]:
    """Derive, filter and deterministically order the raw RDF values of one field."""
    src = spec.source
    if isinstance(src, (URIRef, Path)):
        raw: Iterable[Any] = graph.objects(node, src)
    elif isinstance(src, Sparql):
        raw = src.values(graph, node)
    elif callable(src):
        out = src(graph, node)
        raw = (
            []
            if out is None
            else [out]
            if isinstance(out, (Node, str, int, float, bool))
            else out
        )
    else:
        raise TypeError(f"Unsupported derivation expression: {src!r}")

    values = list(dict.fromkeys(raw))
    if spec.lang is not None:
        values = spec.lang.apply(values)
    if spec.datatype is not None:
        values = [
            v
            for v in values
            if not isinstance(v, Literal) or v.datatype == spec.datatype
        ]

    if spec.order_by is not None:

        def key(v: Any) -> Any:
            first = next(iter(graph.objects(v, spec.order_by)), None)
            return (
                first is None,
                default_converters.convert(first) if first is not None else 0,
            )

        return _sorted(values, key)
    # RDF has no intrinsic ordering: sort for deterministic output
    return _sorted(values, lambda v: default_converters.convert(v))

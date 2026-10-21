"""Per-model field plans: what each field is, how many values it takes, whether it nests."""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin

from semantic_sugar.models.property import IdMarker, PropSpec
from semantic_sugar.models.errors import CardinalityError

MISSING: Any = object()
_CONTAINERS = (list, set, frozenset, tuple)


@dataclass(frozen=True)
class FieldPlan:
    """Describes a single field within an RDFModel so that query results can be shaped correctly.

    It captures the field's name, whether it is the model's identifier, the associated
    RDF property specification, the expected cardinality (one/optional/many), the
    annotation type for a single element, an optional nested RDFModel subclass when the
    element itself is a model, and whether the field is required by Pydantic.
    """

    name: str
    is_id: bool
    spec: PropSpec | None
    cardinality: str  # "one" | "optional" | "many"
    element: Any  # annotation of a single value
    model: type | None  # nested RDFModel subclass, if element is one
    required: bool  # pydantic: field has no default


def _is_model(tp: Any) -> bool:
    return isinstance(tp, type) and getattr(tp, "__rdf_projectable__", False)


def analyze_annotation(ann: Any) -> tuple[str, Any]:
    """Return (cardinality, element annotation) for a field annotation."""
    optional = False
    origin = get_origin(ann)
    if origin in (Union, types.UnionType):
        args = get_args(ann)
        rest = [a for a in args if a is not type(None)]
        optional = len(rest) != len(args)
        if len(rest) == 1:
            ann, origin = rest[0], get_origin(rest[0])
    if origin in _CONTAINERS:
        args = get_args(ann)
        return "many", (args[0] if args else Any)
    return ("optional" if optional else "one"), ann


def build_plan(model: type) -> dict[str, FieldPlan]:
    model.model_rebuild(raise_errors=False)  # resolve forward references
    plan: dict[str, FieldPlan] = {}
    for name, info in model.model_fields.items():
        spec = next(
            (m for m in info.metadata if isinstance(m, PropSpec)), None
        )
        is_id = any(isinstance(m, IdMarker) for m in info.metadata)
        if spec is None and not is_id:
            continue  # not an RDF-derived field
        card, element = analyze_annotation(info.annotation)
        nested = element if _is_model(element) else None
        plan[name] = FieldPlan(
            name,
            is_id,
            spec,
            "one" if is_id else card,
            element,
            nested,
            info.is_required(),
        )
    return plan


def shape(fp: FieldPlan, items: list[Any]) -> Any:
    """Apply the cardinality encoded in the annotation. Returns MISSING to omit the key
    (pydantic then applies the default, or reports the field as required)."""
    if not items:
        if not fp.required:
            return MISSING
        return (
            []
            if fp.cardinality == "many"
            else None
            if fp.cardinality == "optional"
            else MISSING
        )
    if fp.cardinality == "many":
        return items
    if len(items) > 1:
        mode = fp.spec.on_many if fp.spec else "error"
        if mode == "error":
            raise CardinalityError(
                f"expected at most one value for '{fp.name}', got {len(items)}"
            )
        items = [items[0] if mode == "first" else items[-1]]
    return items[0]

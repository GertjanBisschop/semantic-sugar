"""Query-driven projection: SPARQL result rows -> nested model instances."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pydantic import ValidationError

from .converters import default_converters
from .errors import CardinalityError, ProjectionError
from .plan import MISSING, shape


@dataclass(frozen=True)
class Var:
    """Reference to a SPARQL result variable."""
    name: str


def _name(x: Var | str) -> str:
    return x.name if isinstance(x, Var) else x


def _row(r: Any) -> dict[str, Any]:
    return r.asdict() if hasattr(r, "asdict") else dict(r)


@dataclass
class Projection:
    """Maps result variables onto a model, independent of the model's own Props.

    fields: model field name -> Var | str | nested Projection
    key:    variable identifying one object; rows sharing it are merged
            (None: group by the tuple of all directly bound variables)
    """
    model: type
    fields: dict[str, Any]
    key: Var | str | None = None
    query: str | None = None

    # ---- constructors ----------------------------------------------------
    @classmethod
    def by_bind(cls, model: type, bind: dict[str, str], key: str | None = None,
                strict: bool = True) -> "Projection":
        plan = model.rdf_plan()
        id_name = next((n for n, f in plan.items() if f.is_id), None)
        direct: dict[str, Any] = {}
        nested: dict[str, dict[str, str]] = {}
        for path, var in bind.items():
            head, _, rest = path.partition(".")
            if head not in plan:
                if strict:
                    raise KeyError(f"{model.__name__} has no RDF field '{head}'")
                continue
            if rest:
                nested.setdefault(head, {})[rest] = var
            else:
                direct[head] = Var(var)
        for head, sub in nested.items():
            if plan[head].model is None:
                if strict:
                    raise KeyError(f"'{head}' is not a nested model field")
                continue
            direct[head] = cls.by_bind(plan[head].model, sub, None, strict)
        if key is None and id_name in bind:
            key = bind[id_name]
        return cls(model, direct, Var(key) if key else None)

    @classmethod
    def by_convention(cls, model: type, variables: Iterable[str], sep: str = "__") -> "Projection":
        bind = {v.replace(sep, "."): v for v in variables}
        return cls.by_bind(model, bind, strict=False)

    # ---- execution -------------------------------------------------------
    def run(self, graph: Any, **init_bindings: Any) -> list[Any]:
        if self.query is None:
            raise ValueError("Projection has no query; use from_rows()")
        return self.from_rows(graph.query(self.query, initBindings=init_bindings or None))

    def from_rows(self, rows: Iterable[Any], on_error: str = "raise") -> list[Any]:
        return self._build([_row(r) for r in rows], on_error)

    def _group_key(self, row: dict[str, Any]) -> Any:
        if self.key is not None:
            return row.get(_name(self.key))
        vals = tuple(row.get(v.name) for v in self.fields.values() if isinstance(v, Var))
        return vals if any(v is not None for v in vals) else None

    def _build(self, rows: list[dict[str, Any]], on_error: str) -> list[Any]:
        plan = self.model.rdf_plan()
        groups: dict[Any, list[dict[str, Any]]] = {}
        for r in rows:
            k = self._group_key(r)
            if k is not None:
                groups.setdefault(k, []).append(r)
        out: list[Any] = []
        for k, grp in groups.items():
            raw: dict[str, Any] = {}
            try:
                for name, src in self.fields.items():
                    fp = plan[name]
                    if isinstance(src, Projection):
                        items = src._build(grp, on_error)
                    else:
                        vals = dict.fromkeys(r[src.name] for r in grp if r.get(src.name) is not None)
                        items = [default_converters.convert(v) for v in vals]
                    shaped = shape(fp, items)
                    if shaped is not MISSING:
                        raw[name] = shaped
                for name, fp in plan.items():            # fields the query does not provide
                    if name in raw or name in self.fields:
                        continue
                    if fp.is_id:
                        if self.key is not None:         # Id fed by the grouping key
                            raw[name] = k
                    else:
                        shaped = shape(fp, [])           # [] / None / omitted, per annotation
                        if shaped is not MISSING:
                            raw[name] = shaped
                out.append(self.model.model_validate(raw))
            except (ValidationError, CardinalityError) as e:
                if on_error == "raise":
                    raise ProjectionError(k, self.model, None, e) from e
        return out

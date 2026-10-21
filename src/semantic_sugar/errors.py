"""Exceptions and result containers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class semanticError(Exception):
    """Base class for all library errors."""


class CardinalityError(semanticError):
    """A field expecting at most one value received several."""


class CycleError(semanticError):
    """A node was re-entered while it was still being projected."""


class ProjectionError(semanticError):
    """A node could not be projected into a model instance.

    Attributes:
        node:  the RDF node that failed (innermost one for nested failures)
        model: the model class being built for that node
        field: the failing field name, if known
        cause: the underlying exception (often a pydantic ValidationError)
        path:  steps from the root node to the failing node, as
               ``((parent_node, field_name), ...)``
    """

    def __init__(self, node: Any, model: type, field: str | None, cause: BaseException,
                 path: tuple = ()):
        self.node, self.model, self.field, self.cause = node, model, field, cause
        self.path = tuple(path)
        super().__init__(self._message())

    def _message(self) -> str:
        where = " -> ".join(f"{n}.{f}" for n, f in self.path)
        where = f" via {where}" if where else ""
        fld = f".{self.field}" if self.field else ""
        return f"{self.model.__name__}{fld} @ {self.node}{where}: {self.cause}"

    def prepend(self, node: Any, field: str) -> "ProjectionError":
        self.path = ((node, field),) + self.path
        self.args = (self._message(),)
        return self


@dataclass
class ProjectionResult(Generic[T]):
    objects: list[T] = field(default_factory=list)
    errors: list[ProjectionError] = field(default_factory=list)

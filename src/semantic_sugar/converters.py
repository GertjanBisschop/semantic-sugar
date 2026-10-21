"""RDF term -> Python value conversion (pluggable by datatype)."""
from __future__ import annotations

from typing import Any, Callable

from rdflib import Literal, URIRef


class Converters:
    def __init__(self) -> None:
        self._by_datatype: dict[URIRef, Callable[[Literal], Any]] = {}

    def register(self, datatype: URIRef, fn: Callable[[Literal], Any]) -> None:
        self._by_datatype[URIRef(datatype)] = fn

    def convert(self, term: Any) -> Any:
        """Literals become Python values; IRIs / blank nodes stay as they are."""
        if isinstance(term, Literal):
            fn = self._by_datatype.get(term.datatype)
            if fn is not None:
                return fn(term)
            if term.language:
                return str(term)          # plain str, language tag dropped
            return term.toPython()
        return term


default_converters = Converters()

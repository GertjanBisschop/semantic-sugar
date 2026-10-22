from __future__ import annotations

from rdflib.namespace import RDFS

from semantic_sugar import Id, OfType, Prop, RDFModel


class RDFSClass(RDFModel, select=OfType(RDFS.Class)):
    uri: Id

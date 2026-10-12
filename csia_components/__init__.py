"""Cross-component trust for automated platforms. SPECIFICATION, UNVALIDATED.

Read `catalog.UNVALIDATED_CLAIMS` before quoting any number this package
produces. Nothing here has been measured on a real platform, and no frozen
CSIA file is touched by any of it.
"""

from .catalog import FAMILIES, RELATIONS, UNVALIDATED_CLAIMS, by_family, universal
from .combined import (CombinedGraph, ComponentEdge, implicated_by,
                       normalised_residual, relation)

__all__ = ["RELATIONS", "FAMILIES", "UNVALIDATED_CLAIMS", "by_family",
           "universal", "CombinedGraph", "ComponentEdge", "relation",
           "implicated_by", "normalised_residual"]

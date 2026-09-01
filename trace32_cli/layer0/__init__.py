"""Layer 0: thin TRACE32 capability abstractions.

Layer 0 mirrors stable PYRCL/TRACE32 mechanisms. It intentionally does not
implement debugger workflows or architecture-specific debugging strategy.
"""

from .backend import Trace32Backend
from .capabilities import BackendCapabilities
from .errors import BackendErrorCode, Trace32BackendError
from .pyrcl import PyrclBackend

__all__ = [
    "BackendCapabilities",
    "BackendErrorCode",
    "PyrclBackend",
    "Trace32Backend",
    "Trace32BackendError",
]

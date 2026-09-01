"""trace32-cli package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("trace32-cli")
except PackageNotFoundError:
    __version__ = "0+unknown"

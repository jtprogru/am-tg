from importlib.metadata import version

# Single source of truth is pyproject.toml; a hardcoded string here drifted before
__version__ = version("am-tg")

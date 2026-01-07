"""Language plugin registry.

This module provides a central registry for language plugins.
It automatically discovers and registers available plugins.

Usage:
    from src.languages import get_plugin_for_file, get_plugin

    plugin = get_plugin_for_file("example.py")
    if plugin:
        imports = plugin.parse_imports(content)
        calls = plugin.parse_calls(content)
"""

from pathlib import Path

from .base import LanguagePlugin
from .javascript import JavaScriptPlugin
from .php import PHPPlugin
from .python import PythonPlugin

# Plugin registry
_PLUGINS: dict[str, LanguagePlugin] = {}
_EXT_MAP: dict[str, str] = {}


def register(plugin: LanguagePlugin) -> None:
    """Register a language plugin.

    Args:
        plugin: An instance of LanguagePlugin to register.
    """
    _PLUGINS[plugin.name] = plugin
    for ext in plugin.extensions:
        _EXT_MAP[ext] = plugin.name


def get_plugin(language: str) -> LanguagePlugin | None:
    """Get plugin by language name.

    Args:
        language: Language name (e.g., 'python', 'javascript', 'php').

    Returns:
        LanguagePlugin instance or None if not found.
    """
    return _PLUGINS.get(language)


def get_plugin_for_file(file_path: str) -> LanguagePlugin | None:
    """Get plugin for file based on extension.

    Args:
        file_path: Path to the file.

    Returns:
        LanguagePlugin instance or None if extension not supported.
    """
    ext = Path(file_path).suffix.lower()
    lang = _EXT_MAP.get(ext)
    return _PLUGINS.get(lang) if lang else None


def get_supported_extensions() -> frozenset[str]:
    """Get all supported file extensions.

    Returns:
        Frozenset of supported extensions (e.g., {'.py', '.js', '.ts'}).
    """
    return frozenset(_EXT_MAP.keys())


def get_supported_languages() -> frozenset[str]:
    """Get all supported language names.

    Returns:
        Frozenset of supported languages (e.g., {'python', 'javascript', 'php'}).
    """
    return frozenset(_PLUGINS.keys())


# Register plugins at import time
register(PythonPlugin())
register(JavaScriptPlugin())
register(PHPPlugin())

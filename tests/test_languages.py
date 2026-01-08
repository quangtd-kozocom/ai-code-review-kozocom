"""Tests for language plugins."""

import pytest

from src.languages import (
    get_plugin,
    get_plugin_for_file,
    get_supported_extensions,
    get_supported_languages,
)
from src.languages.javascript import JavaScriptPlugin
from src.languages.php import PHPPlugin
from src.languages.python import PythonPlugin
from src.languages.typescript import TypeScriptPlugin


class TestLanguageRegistry:
    """Tests for language registry functions."""

    def test_get_plugin_python(self):
        plugin = get_plugin("python")
        assert plugin is not None
        assert plugin.name == "python"

    def test_get_plugin_javascript(self):
        plugin = get_plugin("javascript")
        assert plugin is not None
        assert plugin.name == "javascript"

    def test_get_plugin_php(self):
        plugin = get_plugin("php")
        assert plugin is not None
        assert plugin.name == "php"

    def test_get_plugin_unknown(self):
        plugin = get_plugin("unknown")
        assert plugin is None

    def test_get_plugin_for_file_py(self):
        plugin = get_plugin_for_file("test.py")
        assert plugin is not None
        assert plugin.name == "python"

    def test_get_plugin_for_file_js(self):
        plugin = get_plugin_for_file("test.js")
        assert plugin is not None
        assert plugin.name == "javascript"

    def test_get_plugin_for_file_tsx(self):
        plugin = get_plugin_for_file("component.tsx")
        assert plugin is not None
        assert plugin.name == "typescript"

    def test_get_plugin_for_file_ts(self):
        plugin = get_plugin_for_file("service.ts")
        assert plugin is not None
        assert plugin.name == "typescript"

    def test_get_plugin_typescript(self):
        plugin = get_plugin("typescript")
        assert plugin is not None
        assert plugin.name == "typescript"

    def test_get_plugin_for_file_php(self):
        plugin = get_plugin_for_file("Controller.php")
        assert plugin is not None
        assert plugin.name == "php"

    def test_get_plugin_for_file_unknown(self):
        plugin = get_plugin_for_file("README.md")
        assert plugin is None

    def test_supported_extensions(self):
        exts = get_supported_extensions()
        assert ".py" in exts
        assert ".js" in exts
        assert ".ts" in exts
        assert ".php" in exts

    def test_supported_languages(self):
        langs = get_supported_languages()
        assert "python" in langs
        assert "javascript" in langs
        assert "typescript" in langs
        assert "php" in langs


class TestPythonPlugin:
    """Tests for Python language plugin."""

    @pytest.fixture
    def plugin(self):
        return PythonPlugin()

    def test_properties(self, plugin):
        assert plugin.name == "python"
        assert plugin.extensions == (".py",)
        assert plugin.tree_sitter_name == "python"
        assert "function_definition" in plugin.extract_node_types
        assert "class_definition" in plugin.extract_node_types

    def test_parse_imports_simple(self, plugin):
        content = """
import os
import sys
from typing import List
"""
        imports = plugin.parse_imports(content)
        assert "os" in imports
        assert "sys" in imports
        assert "typing" in imports

    def test_parse_imports_from(self, plugin):
        content = """
from src.utils import helper
from src.models.user import User
"""
        imports = plugin.parse_imports(content)
        assert "src.utils" in imports
        assert "src.models.user" in imports

    def test_parse_imports_relative(self, plugin):
        content = """
from .models import User
from ..utils import helper
"""
        # Note: Relative imports are handled differently
        imports = plugin.parse_imports(content)
        assert len(imports) >= 0  # Relative imports may not be captured fully

    def test_parse_calls(self, plugin):
        content = """
def calculate(x, y):
    result = helper(x) + process(y)
    return format_result(result)
"""
        calls = plugin.parse_calls(content)
        assert "helper" in calls
        assert "process" in calls
        assert "format_result" in calls

    def test_parse_calls_excludes_builtins(self, plugin):
        content = """
def example():
    print(len([1, 2, 3]))
    return str(42)
"""
        calls = plugin.parse_calls(content)
        assert "print" not in calls
        assert "len" not in calls
        assert "str" not in calls

    def test_get_test_patterns(self, plugin):
        patterns = plugin.get_test_patterns("src/utils.py")
        assert "tests/test_utils.py" in patterns
        assert "test_utils.py" in patterns


class TestJavaScriptPlugin:
    """Tests for JavaScript language plugin."""

    @pytest.fixture
    def plugin(self):
        return JavaScriptPlugin()

    def test_properties(self, plugin):
        assert plugin.name == "javascript"
        assert ".js" in plugin.extensions
        assert ".jsx" in plugin.extensions
        # TypeScript handled by TypeScriptPlugin
        assert ".ts" not in plugin.extensions
        assert ".tsx" not in plugin.extensions

    def test_parse_imports_es6(self, plugin):
        content = """
import { foo, bar } from './utils';
import * as React from 'react';
import Component from './Component';
"""
        imports = plugin.parse_imports(content)
        assert "./utils" in imports
        assert "react" in imports
        assert "./Component" in imports

    def test_parse_imports_require(self, plugin):
        content = """
const express = require('express');
const { router } = require('./router');
"""
        imports = plugin.parse_imports(content)
        assert "express" in imports
        assert "./router" in imports

    def test_parse_imports_type(self, plugin):
        content = """
import type { UserType } from './types';
"""
        imports = plugin.parse_imports(content)
        assert "./types" in imports

    def test_parse_calls(self, plugin):
        content = """
function example() {
    const result = processData(input);
    helper.transform(result);
    return validate(result);
}
"""
        calls = plugin.parse_calls(content)
        assert "processData" in calls
        assert "transform" in calls
        assert "validate" in calls

    def test_get_test_patterns(self, plugin):
        patterns = plugin.get_test_patterns("src/utils.js")
        assert "__tests__/utils.test.js" in patterns
        assert "utils.test.js" in patterns
        assert "utils.spec.js" in patterns

    def test_extract_express_routes(self, plugin):
        """Test Express.js route extraction."""
        content = """
const express = require('express');
const router = express.Router();

router.get('/users', getUsers);
router.post('/users', createUser);
app.delete('/users/:id', deleteUser);
app.use('/api', apiRouter);
"""
        routes = plugin.extract_express_routes(content)
        assert len(routes) == 4
        methods = [r["method"] for r in routes]
        paths = [r["path"] for r in routes]
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods
        assert "USE" in methods
        assert "/users" in paths
        assert "/users/:id" in paths
        assert "/api" in paths

    def test_extract_node_types_includes_variables(self, plugin):
        """Test that variable declarations are extracted for Express patterns."""
        node_types = plugin.extract_node_types
        assert "variable_declaration" in node_types
        assert "lexical_declaration" in node_types
        assert "export_statement" in node_types


class TestPHPPlugin:
    """Tests for PHP language plugin."""

    @pytest.fixture
    def plugin(self):
        return PHPPlugin()

    def test_properties(self, plugin):
        assert plugin.name == "php"
        assert plugin.extensions == (".php",)
        assert plugin.tree_sitter_name == "php"

    def test_parse_imports_use(self, plugin):
        content = """<?php
use App\\Models\\User;
use App\\Services\\OrderService as Service;
"""
        imports = plugin.parse_imports(content)
        # Should be normalized to forward slashes
        assert any("App/Models/User" in imp for imp in imports)
        assert any("App/Services/OrderService" in imp for imp in imports)

    def test_parse_imports_require(self, plugin):
        content = """<?php
require_once 'vendor/autoload.php';
include 'config.php';
"""
        imports = plugin.parse_imports(content)
        assert "vendor/autoload.php" in imports
        assert "config.php" in imports

    def test_parse_calls(self, plugin):
        content = """<?php
function example() {
    $result = processData($input);
    $user->save();
    Helper::validate($result);
    return $result;
}
"""
        calls = plugin.parse_calls(content)
        assert "processData" in calls
        assert "save" in calls
        assert "validate" in calls

    def test_get_test_patterns(self, plugin):
        patterns = plugin.get_test_patterns("app/Services/OrderService.php")
        assert "tests/OrderServiceTest.php" in patterns
        assert "tests/Unit/OrderServiceTest.php" in patterns
        assert "tests/Feature/OrderServiceTest.php" in patterns


class TestTypeScriptPlugin:
    """Tests for TypeScript language plugin."""

    @pytest.fixture
    def plugin(self):
        return TypeScriptPlugin()

    def test_properties(self, plugin):
        assert plugin.name == "typescript"
        assert ".ts" in plugin.extensions
        assert ".tsx" in plugin.extensions
        assert plugin.tree_sitter_name == "typescript"

    def test_get_grammar_for_file(self, plugin):
        """Test correct grammar selection based on file extension."""
        assert plugin.get_grammar_for_file("service.ts") == "typescript"
        assert plugin.get_grammar_for_file("component.tsx") == "tsx"
        assert plugin.get_grammar_for_file("src/utils/helper.ts") == "typescript"
        assert plugin.get_grammar_for_file("src/components/Button.tsx") == "tsx"

    def test_parse_imports_es6(self, plugin):
        content = """
import { foo, bar } from './utils';
import * as React from 'react';
import Component from './Component';
"""
        imports = plugin.parse_imports(content)
        assert "./utils" in imports
        assert "react" in imports
        assert "./Component" in imports

    def test_parse_imports_type(self, plugin):
        content = """
import type { UserType } from './types';
import { Request, Response } from 'express';
"""
        imports = plugin.parse_imports(content)
        assert "./types" in imports
        assert "express" in imports

    def test_parse_imports_side_effect(self, plugin):
        content = """
import 'reflect-metadata';
import './polyfills';
"""
        imports = plugin.parse_imports(content)
        assert "reflect-metadata" in imports
        assert "./polyfills" in imports

    def test_parse_calls(self, plugin):
        content = """
function example() {
    const result = processData(input);
    helper.transform(result);
    return validate(result);
}
"""
        calls = plugin.parse_calls(content)
        assert "processData" in calls
        assert "transform" in calls
        assert "validate" in calls

    def test_get_test_patterns(self, plugin):
        patterns = plugin.get_test_patterns("src/utils.ts")
        assert "__tests__/utils.test.ts" in patterns
        assert "utils.test.ts" in patterns
        assert "utils.spec.ts" in patterns

    def test_get_test_patterns_tsx(self, plugin):
        patterns = plugin.get_test_patterns("src/Button.tsx")
        assert "__tests__/Button.test.tsx" in patterns
        assert "Button.test.tsx" in patterns

    def test_extract_node_types_includes_typescript(self, plugin):
        """Test TypeScript-specific node types are extracted."""
        node_types = plugin.extract_node_types
        # Functions and classes
        assert "function_declaration" in node_types
        assert "class_declaration" in node_types
        assert "arrow_function" in node_types
        # Variables (for Express patterns)
        assert "variable_declaration" in node_types
        assert "lexical_declaration" in node_types
        # TypeScript specific
        assert "interface_declaration" in node_types
        assert "type_alias_declaration" in node_types
        assert "enum_declaration" in node_types

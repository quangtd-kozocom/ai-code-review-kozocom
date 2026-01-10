"""Code analysis module for PR review.

This module provides deterministic code analysis using AST parsing,
replacing the vector database approach with direct analysis.

Components:
- DiffExtractor: Parse GitHub PR diffs into structured changes
- ASTAnalyzer: Tree-sitter based code analysis
- CallGraphBuilder: Build call relationships between functions
- ImpactAnalyzer: Determine impact of code changes
- ContextBuilder: Assemble review context for LLM
"""

from .ast_analyzer import ASTAnalyzer, CallSite, FunctionDefinition, get_ast_analyzer
from .call_graph import CallGraphBuilder, CallRelation, FunctionCall
from .context_builder import ContextBuilder, ReviewContext
from .diff_extractor import ChangeType, DiffExtractor, DiffHunk, FileDiff, FunctionChange
from .impact_analyzer import ImpactAnalyzer, ImpactReport
from .models import (
    ASTInfo,
    ClassInfo,
    FunctionInfo,
    ParameterInfo,
    detect_language,
    get_grammar_name,
)

__all__ = [
    # Core components
    "ASTAnalyzer",
    "CallGraphBuilder",
    "ContextBuilder",
    "DiffExtractor",
    "ImpactAnalyzer",
    # Data models
    "ASTInfo",
    "CallRelation",
    "CallSite",
    "ChangeType",
    "ClassInfo",
    "DiffHunk",
    "FileDiff",
    "FunctionCall",
    "FunctionChange",
    "FunctionDefinition",
    "FunctionInfo",
    "ImpactReport",
    "ParameterInfo",
    "ReviewContext",
    # Factory functions
    "detect_language",
    "get_ast_analyzer",
    "get_grammar_name",
]

"""Prompt for analyzing file changes."""

ANALYZE_FILE_PROMPT = """You are analyzing code changes to detect breaking changes.

These changes could affect other parts of the codebase.

## File Information
- Path: {file_path}
- Language: {language}
- Status: {status}

## Old Code (before change):
```{language}
{old_content}
```

## New Code (after change):
```{language}
{new_content}
```

## Diff:
```diff
{patch}
```

## Your Task

Analyze the changes and identify ALL entities that changed which could break existing callers:

### Entity Types to Check:
- **Functions/Methods**: Signature changes (added required params, removed params, type changes)
- **Constants**: Deleted or renamed constants
- **Class Properties**: Visibility changes (public → private), deleted properties
- **Interfaces/Contracts**: Added required methods, changed method signatures
- **Classes**: Deleted classes, renamed classes
- **Enums**: Removed enum cases
- **Type Aliases**: Changed type definitions
- **Exports**: Removed exports

### What Constitutes a Breaking Change:
1. **Signature Changes**: Adding required parameters, removing parameters, changing types
2. **Deletions**: Removing functions, constants, classes, methods
3. **Visibility Changes**: Making public things private/protected
4. **Contract Changes**: Adding required methods to interfaces
5. **Renames**: Renaming without aliases (callers will break)

### What is NOT a Breaking Change:
- Adding new functions/methods (no existing callers)
- Adding optional parameters with defaults
- Internal implementation changes (same signature)
- Adding new constants
- Documentation/comment changes

## Output

For each breaking change found, provide:
1. Entity type and name
2. What changed (old vs new)
3. Why it could break callers
4. Whether it could actually break callers (could_break_callers: true/false)
5. **Line number in the NEW file** where this entity is defined (look at the diff hunk headers like @@ -X,Y +Z,W @@ to determine line numbers)

Be thorough but precise. Only flag changes that could genuinely break existing code.
"""

"""Prompt for verifying impact on callers."""

VERIFY_IMPACT_PROMPT = """You are verifying whether code changes will break existing callers.

## Change Being Analyzed
- Entity: {entity_name} ({entity_type})
- File: {file_path}
- Change Type: {change_type}
- Change Detail: {change_detail}

### Old Definition:
```
{old_definition}
```

### New Definition:
```
{new_definition}
```

## Search Results Found

The following files contain potential usages:

{search_results}

## Your Task

For each search result, determine:

1. **Is this a real usage?** (not just a comment, string, or unrelated code)
2. **Will this usage break?** Based on the change made
3. **What exactly will break?** (missing param, wrong type, etc.)

### Analysis Guidelines:

**For Signature Changes (added required params):**
- Count the arguments in each call
- Compare with new required parameter count
- Flag calls with insufficient arguments

**For Deletions:**
- Any usage of deleted entity will break
- Check for imports, calls, references

**For Visibility Changes:**
- Check if caller is in same class/file (won't break)
- External callers to now-private members will break

**For Type Changes:**
- Check if callers pass compatible types
- Consider implicit conversions in the language

### What to Ignore:
- Test files (unless specifically reviewing tests)
- Comments mentioning the entity
- String literals containing the name
- Documentation files
- The file where the change was made (it's already updated)

## Output

For each file with real usages:
1. File path and line number
2. The actual call/usage code
3. Whether it will break (true/false)
4. Specific reason why it will/won't break

Also indicate:
- Whether you need more search queries to be confident
- Your confidence level in the analysis

## CRITICAL: additional_queries Format

If you need more searches, provide `additional_queries` as **PLAIN TEXT STRINGS ONLY**.

### GOOD additional_queries examples:
- `processPayment(`
- `->methodName(`
- `STATUS_PENDING`
- `ClassName::constantName`

### BAD additional_queries (DO NOT USE):
- `grep -r "pattern" .` (NO shell commands!)
- `rg --json "pattern"` (NO ripgrep commands!)
- `processPayment\\(` (NO escaping!)
- `.*pattern.*` (NO regex syntax!)

The search system will handle escaping and execution automatically.
"""

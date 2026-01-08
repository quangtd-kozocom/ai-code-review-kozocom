"""Smart router prompt for content-aware agent routing."""

PROMPT = """Analyze the CODE CONTENT of each file to determine which review agents should run.

## Step 1: Detect Code Signals
For each file, identify these signals from the ACTUAL CODE (not just filename):

**Security Signals:**
- User input handling (request.args, request.form, input(), sys.argv)
- Database operations (execute, query, cursor, ORM queries)
- Authentication/authorization (login, token, session, password, jwt)
- External calls (requests, urllib, subprocess, os.system, eval, exec)
- File operations with user paths (open, read, write with variables)
- Cryptography usage (hash, encrypt, secret, key)

**Logic Signals:**
- Complex conditionals (nested if/else, multiple conditions)
- Loop operations (for, while with break/continue)
- Error handling (try/except, raise)
- Data transformations (map, filter, list comprehensions)
- State mutations (assignments, updates)
- Null/None checks or lack thereof

**Style Signals:**
- Magic numbers/strings (hardcoded values without constants)
- Function/variable naming patterns
- Missing type hints
- Long functions (many lines in diff)
- Missing docstrings

## Step 2: Map Signals to Agents
- If ANY security signal detected → include "security"
- If logic signals detected → include "logic"  
- If style signals AND not a test file → include "style"

## Files to Analyze
{files_content}

For each file, output the detected signals and resulting agent decision.
"""

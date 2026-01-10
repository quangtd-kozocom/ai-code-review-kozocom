"""Constants for the code review agent."""

# ═══════════════════════════════════════════════════════════════════════════════
# Entity Types (detected by LLM)
# ═══════════════════════════════════════════════════════════════════════════════

ENTITY_FUNCTION = "function"
ENTITY_METHOD = "method"
ENTITY_CONSTANT = "constant"
ENTITY_PROPERTY = "property"
ENTITY_INTERFACE = "interface"
ENTITY_CLASS = "class"
ENTITY_ENUM = "enum"
ENTITY_TYPE = "type"

# ═══════════════════════════════════════════════════════════════════════════════
# Change Types (detected by LLM)
# ═══════════════════════════════════════════════════════════════════════════════

CHANGE_SIGNATURE = "signature_changed"
CHANGE_DELETED = "deleted"
CHANGE_VALUE = "value_changed"
CHANGE_VISIBILITY = "visibility_changed"
CHANGE_CONTRACT = "contract_changed"
CHANGE_RENAMED = "renamed"

# ═══════════════════════════════════════════════════════════════════════════════
# File Status
# ═══════════════════════════════════════════════════════════════════════════════

FILE_ADDED = "added"
FILE_MODIFIED = "modified"
FILE_DELETED = "deleted"
FILE_RENAMED = "renamed"

# ═══════════════════════════════════════════════════════════════════════════════
# Severity Levels
# ═══════════════════════════════════════════════════════════════════════════════

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Threshold for critical severity (number of affected callers)
CRITICAL_CALLER_THRESHOLD = 3

# ═══════════════════════════════════════════════════════════════════════════════
# Search Configuration
# ═══════════════════════════════════════════════════════════════════════════════

MAX_SEARCH_ITERATIONS = 3
MAX_RESULTS_PER_QUERY = 20
SEARCH_CONTEXT_LINES = 3

# Directories to always exclude from search
SEARCH_EXCLUDE_DIRS = [
    "**/node_modules/**",
    "**/vendor/**",
    "**/.git/**",
    "**/dist/**",
    "**/build/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/coverage/**",
]

# ═══════════════════════════════════════════════════════════════════════════════
# Clone Configuration
# ═══════════════════════════════════════════════════════════════════════════════

CLONE_DEPTH = 1
CLONE_BLOB_LIMIT = "1m"  # Skip files larger than 1MB

# ═══════════════════════════════════════════════════════════════════════════════
# Code File Extensions
# ═══════════════════════════════════════════════════════════════════════════════

CODE_EXTENSIONS = frozenset({
    ".py", ".php", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".swift", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs",
})

# ═══════════════════════════════════════════════════════════════════════════════
# Graph Node Names
# ═══════════════════════════════════════════════════════════════════════════════

NODE_EXTRACT_DIFF = "extract_diff"
NODE_CLONE_REPO = "clone_repo"
NODE_GET_NEXT_FILE = "get_next_file"
NODE_ANALYZE_FILE = "analyze_file"
NODE_PLAN_SEARCH = "plan_search"
NODE_EXECUTE_SEARCH = "execute_search"
NODE_VERIFY_IMPACT = "verify_impact"
NODE_NEXT_CHANGE = "next_change"
NODE_GENERATE_REVIEW = "generate_review"
NODE_PUBLISH_GITHUB = "publish_github"
NODE_PUBLISH_SUMMARY = "publish_summary"
NODE_CLEANUP = "cleanup"

# ═══════════════════════════════════════════════════════════════════════════════
# Routing Targets
# ═══════════════════════════════════════════════════════════════════════════════

ROUTE_END = "end"

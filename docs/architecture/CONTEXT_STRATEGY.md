# Context Strategy for PR Review

> **Document Version**: 2.0  
> **Last Updated**: January 2026

## Table of Contents

1. [Context Philosophy](#context-philosophy)
2. [Modified Files Strategy](#modified-files-strategy)
3. [New Files Strategy](#new-files-strategy)
4. [Deleted Files Strategy](#deleted-files-strategy)
5. [Cross-File Analysis](#cross-file-analysis)
6. [Context Assembly Examples](#context-assembly-examples)

---

## Context Philosophy

### Core Principle

> **Precise context beats more context.**

The old system failed because it provided "related" code that was:
- From the wrong branch
- Semantically similar but not actually relevant
- Missing explicit relationship information

The new system provides:
- Exact code from both source and target branches
- Explicit call relationships (who calls what)
- Specific questions based on the type of change

### Context Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT TRUST LEVELS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LEVEL 1: GROUND TRUTH (100% trust)                                         │
│  ─────────────────────────────────                                           │
│  • The actual diff                                                           │
│  • Old code from target branch                                               │
│  • New code from source branch                                               │
│  • Line numbers and file paths                                               │
│                                                                              │
│  LEVEL 2: DIRECT RELATIONSHIPS (95% trust)                                  │
│  ───────────────────────────────────────────                                 │
│  • Functions that directly call the changed function                        │
│  • Functions that the changed function directly calls                       │
│  • Tests that specifically test the changed function                        │
│                                                                              │
│  LEVEL 3: INDIRECT RELATIONSHIPS (80% trust)                                │
│  ────────────────────────────────────────────                                │
│  • Transitive callers (2 levels deep)                                       │
│  • Similar function signatures in codebase                                  │
│  • Related configuration files                                              │
│                                                                              │
│  LEVEL 4: INFERRED CONTEXT (60% trust)                                      │
│  ──────────────────────────────────────                                      │
│  • Naming conventions suggesting relationship                               │
│  • Same module/package membership                                           │
│  • Similar code patterns (from vector search)                               │
│                                                                              │
│  ❌ NOT INCLUDED (0% trust)                                                 │
│  ───────────────────────────                                                 │
│  • Code from wrong branch                                                   │
│  • Semantically similar but unrelated code                                  │
│  • "Might be relevant" guesses                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Modified Files Strategy

### How We Extract the Diff

```python
# src/analysis/diff_extractor.py

class DiffExtractor:
    """Extract structured diff information from GitHub PR."""
    
    async def extract_file_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        file_path: str,
    ) -> FileDiff:
        """
        Extract diff for a single file.
        
        Process:
        1. Get patch from PR files endpoint
        2. Parse unified diff format
        3. Map line numbers to content
        """
        # Get PR file info
        pr_file = await self.github.get_pr_file(owner, repo, pr_number, file_path)
        
        # Parse the patch
        hunks = self._parse_patch(pr_file.patch)
        
        return FileDiff(
            path=file_path,
            status=pr_file.status,
            hunks=hunks,
            additions=pr_file.additions,
            deletions=pr_file.deletions,
        )
    
    def _parse_patch(self, patch: str) -> list[DiffHunk]:
        """
        Parse unified diff format.
        
        Example patch:
        @@ -10,6 +10,8 @@
         def calculate_rewards(user_id: int) -> float:
        +    multiplier: float = 1.0,
        +) -> float:
             user = get_user(user_id)
        """
        hunks = []
        current_hunk = None
        
        for line in patch.split('\n'):
            if line.startswith('@@'):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                if match:
                    current_hunk = DiffHunk(
                        old_start=int(match.group(1)),
                        new_start=int(match.group(3)),
                        lines=[],
                    )
                    hunks.append(current_hunk)
            elif current_hunk:
                current_hunk.lines.append(DiffLine(
                    type='add' if line.startswith('+') else 'del' if line.startswith('-') else 'context',
                    content=line[1:] if line else '',
                ))
        
        return hunks
```

### How Much Surrounding Context

```python
# Context window configuration
CONTEXT_CONFIG = {
    # Lines before/after changed code to include
    "surrounding_lines": 5,
    
    # For function-level context
    "include_full_function": True,
    
    # For callers
    "caller_context_lines": 5,  # Lines around call site
    
    # Maximum context per function
    "max_context_tokens": 2000,
}
```

### Identifying Impacted Functions

```python
# src/analysis/ast_analyzer.py

class ASTAnalyzer:
    """Tree-sitter based code analysis."""
    
    def identify_changed_functions(
        self,
        old_code: str,
        new_code: str,
        diff_hunks: list[DiffHunk],
        language: str,
    ) -> list[FunctionChange]:
        """
        Identify which functions were actually changed.
        
        Process:
        1. Parse both versions with tree-sitter
        2. Extract all functions from both
        3. Compare by:
           a. Name (added/deleted functions)
           b. Content (modified functions)
        4. Correlate with diff line numbers
        """
        old_functions = self.extract_functions(old_code, language)
        new_functions = self.extract_functions(new_code, language)
        
        old_by_name = {f.name: f for f in old_functions}
        new_by_name = {f.name: f for f in new_functions}
        
        changes = []
        
        # Find added/modified functions
        for name, new_func in new_by_name.items():
            if name not in old_by_name:
                changes.append(FunctionChange(
                    name=name,
                    change_type="added",
                    old_code=None,
                    new_code=new_func.code,
                    line_range=new_func.line_range,
                ))
            elif new_func.code != old_by_name[name].code:
                changes.append(FunctionChange(
                    name=name,
                    change_type="modified",
                    old_code=old_by_name[name].code,
                    new_code=new_func.code,
                    old_signature=old_by_name[name].signature,
                    new_signature=new_func.signature,
                    line_range=new_func.line_range,
                ))
        
        # Find deleted functions
        for name, old_func in old_by_name.items():
            if name not in new_by_name:
                changes.append(FunctionChange(
                    name=name,
                    change_type="deleted",
                    old_code=old_func.code,
                    new_code=None,
                    line_range=old_func.line_range,
                ))
        
        return changes
```

---

## New Files Strategy

### Analyzing Dependencies in New Files

```python
# src/analysis/dependency_analyzer.py

class DependencyAnalyzer:
    """Analyze dependencies of new files."""
    
    async def analyze_new_file(
        self,
        file_path: str,
        file_content: str,
        repo_files: dict[str, str],
        language: str,
    ) -> NewFileAnalysis:
        """
        Analyze a completely new file.
        
        For new files, we need to understand:
        1. What existing code does it use?
        2. Does it use that code correctly?
        3. Does it follow existing patterns?
        """
        parser = ASTAnalyzer()
        
        # Extract what the new file imports/uses
        imports = parser.extract_imports(file_content, language)
        calls = parser.extract_all_calls(file_content, language)
        
        dependencies = []
        
        for call in calls:
            # Find where this function is defined
            definition = self._find_definition(call, repo_files, language)
            
            if definition:
                dependencies.append(Dependency(
                    used_function=call,
                    defined_in=definition.file_path,
                    definition_code=definition.code,
                    signature=definition.signature,
                    usage_in_new_file=self._find_usage_context(
                        file_content, call, lines=3
                    ),
                ))
        
        return NewFileAnalysis(
            file_path=file_path,
            imports=imports,
            dependencies=dependencies,
            functions_defined=parser.extract_functions(file_content, language),
        )
    
    def _find_definition(
        self,
        function_name: str,
        repo_files: dict[str, str],
        language: str,
    ) -> FunctionInfo | None:
        """Find where a function is defined in the codebase."""
        parser = ASTAnalyzer()
        
        for file_path, content in repo_files.items():
            functions = parser.extract_functions(content, language)
            for func in functions:
                if func.name == function_name:
                    return func
        
        return None
```

### Detecting Usage of Existing Code

```python
# Example: New file payments/stripe_integration.py

# The analyzer extracts:
{
    "imports": [
        "from payments.processor import PaymentProcessor",
        "from core.models import Transaction",
    ],
    "calls_to_existing_code": [
        {
            "function": "PaymentProcessor.process",
            "defined_in": "payments/processor.py",
            "signature": "(self, amount: float, currency: str) -> TransactionResult",
            "usage_in_new_file": "result = self.processor.process(amount, 'USD')",
            "validation": {
                "params_match": True,
                "return_type_used_correctly": True,
            }
        },
        {
            "function": "Transaction.create",
            "defined_in": "core/models.py",
            "signature": "(cls, **kwargs) -> Transaction",
            "usage_in_new_file": "txn = Transaction.create(amount=100)",
        }
    ],
}
```

### Validating Function Calls

```python
# src/analysis/call_validator.py

class CallValidator:
    """Validate that function calls match signatures."""
    
    def validate_call(
        self,
        call_site: CallSite,
        definition: FunctionInfo,
    ) -> list[ValidationIssue]:
        """
        Check if a function call matches the expected signature.
        
        Checks:
        1. Required parameters provided
        2. Parameter types compatible
        3. Return value used correctly
        """
        issues = []
        
        # Parse the call site
        call_args = self._parse_call_args(call_site.code)
        expected_params = self._parse_signature(definition.signature)
        
        # Check required params
        for param in expected_params:
            if param.required and param.name not in call_args:
                issues.append(ValidationIssue(
                    type="missing_required_param",
                    message=f"Missing required parameter: {param.name}",
                    location=call_site.line,
                ))
        
        # Check for extra params
        param_names = {p.name for p in expected_params}
        for arg_name in call_args:
            if arg_name not in param_names and not any(p.is_kwargs for p in expected_params):
                issues.append(ValidationIssue(
                    type="unexpected_param",
                    message=f"Unexpected parameter: {arg_name}",
                    location=call_site.line,
                ))
        
        return issues
```

### Identifying Conflicts with Existing Code

```python
# src/analysis/conflict_detector.py

class ConflictDetector:
    """Detect potential conflicts between new and existing code."""
    
    def detect_conflicts(
        self,
        new_file: NewFileAnalysis,
        repo_files: dict[str, str],
    ) -> list[PotentialConflict]:
        """
        Detect if new code conflicts with existing patterns.
        
        Example: stripe_integration.py might conflict with paypal_integration.py
        if they both try to:
        - Use the same database table differently
        - Define similar function names
        - Compete for shared resources
        """
        conflicts = []
        
        # Find similar files (same directory, similar name)
        similar_files = self._find_similar_files(new_file.file_path, repo_files)
        
        for similar_path, similar_content in similar_files:
            similar_analysis = self._analyze_file(similar_content)
            
            # Check for function name conflicts
            new_func_names = {f.name for f in new_file.functions_defined}
            similar_func_names = {f.name for f in similar_analysis.functions}
            
            overlap = new_func_names & similar_func_names
            if overlap:
                conflicts.append(PotentialConflict(
                    type="function_name_conflict",
                    message=f"Functions {overlap} also defined in {similar_path}",
                    files=[new_file.file_path, similar_path],
                ))
            
            # Check for shared resource conflicts
            new_resources = self._extract_resources(new_file)
            similar_resources = self._extract_resources(similar_analysis)
            
            shared = new_resources & similar_resources
            if shared:
                conflicts.append(PotentialConflict(
                    type="shared_resource",
                    message=f"Both files use {shared}",
                    files=[new_file.file_path, similar_path],
                    recommendation="Ensure consistent usage patterns",
                ))
        
        return conflicts
```

---

## Deleted Files Strategy

### Detecting Dangling References

```python
# src/analysis/deletion_analyzer.py

class DeletionAnalyzer:
    """Analyze impact of deleted files."""
    
    async def analyze_deletion(
        self,
        deleted_file: str,
        deleted_content: str,
        repo_files: dict[str, str],
        language: str,
    ) -> DeletionImpact:
        """
        Analyze what breaks when a file is deleted.
        
        Checks:
        1. What functions/classes were exported?
        2. Who imports from this file?
        3. Who calls functions from this file?
        """
        parser = ASTAnalyzer()
        call_graph = CallGraphBuilder()
        
        # What was in the deleted file
        deleted_functions = parser.extract_functions(deleted_content, language)
        deleted_classes = parser.extract_classes(deleted_content, language)
        
        # Find references to deleted code
        broken_imports = []
        broken_calls = []
        
        for file_path, content in repo_files.items():
            # Check imports
            imports = parser.extract_imports(content, language)
            for imp in imports:
                if self._imports_from(imp, deleted_file):
                    broken_imports.append(BrokenImport(
                        file=file_path,
                        import_statement=imp,
                        imported_from=deleted_file,
                    ))
            
            # Check function calls
            for func in deleted_functions:
                callers = call_graph.find_callers(func.name, {file_path: content})
                for caller in callers:
                    broken_calls.append(BrokenCall(
                        file=file_path,
                        caller_function=caller.function_name,
                        deleted_function=func.name,
                        line=caller.line_number,
                    ))
        
        return DeletionImpact(
            deleted_file=deleted_file,
            deleted_functions=[f.name for f in deleted_functions],
            deleted_classes=[c.name for c in deleted_classes],
            broken_imports=broken_imports,
            broken_calls=broken_calls,
        )
```

### Warning About Breaking Changes

```python
# Context provided to LLM for deleted files

DELETED_FILE_CONTEXT_TEMPLATE = """
## ⚠️ FILE DELETED: {file_path}

### What Was Deleted:
- Functions: {function_list}
- Classes: {class_list}

### Breaking References Found:

#### Broken Imports ({import_count}):
{broken_imports_detail}

#### Broken Function Calls ({call_count}):
{broken_calls_detail}

### Questions for Review:
1. Are all broken imports addressed in this PR?
2. Are the deleted functions replaced with alternatives?
3. Is this deletion intentional or accidental?
"""
```

---

## Cross-File Analysis

### Building the Dependency Graph

```python
# src/analysis/dependency_graph.py

class DependencyGraphBuilder:
    """Build a complete dependency graph for changed code."""
    
    def build_graph(
        self,
        changed_functions: list[FunctionChange],
        repo_files: dict[str, str],
        language: str,
    ) -> DependencyGraph:
        """
        Build bi-directional dependency graph.
        
        Graph includes:
        - Changed functions (nodes)
        - Callers → Changed (edges)
        - Changed → Callees (edges)
        - Test → Changed (edges)
        """
        graph = DependencyGraph()
        parser = ASTAnalyzer()
        
        for func in changed_functions:
            # Add node for changed function
            node = graph.add_node(
                id=f"{func.file_path}:{func.name}",
                type="changed",
                data=func,
            )
            
            # Find and add callers
            callers = self._find_callers(func.name, repo_files, parser)
            for caller in callers:
                caller_node = graph.add_node(
                    id=f"{caller.file_path}:{caller.function_name}",
                    type="caller",
                    data=caller,
                )
                graph.add_edge(caller_node, node, type="calls")
            
            # Find and add callees
            callees = self._find_callees(func.new_code or func.old_code, parser)
            for callee_name in callees:
                callee_def = self._find_definition(callee_name, repo_files, parser)
                if callee_def:
                    callee_node = graph.add_node(
                        id=f"{callee_def.file_path}:{callee_name}",
                        type="callee",
                        data=callee_def,
                    )
                    graph.add_edge(node, callee_node, type="calls")
            
            # Find tests
            tests = self._find_tests(func.name, repo_files)
            for test in tests:
                test_node = graph.add_node(
                    id=f"{test.file_path}:{test.name}",
                    type="test",
                    data=test,
                )
                graph.add_edge(test_node, node, type="tests")
        
        return graph
```

### Visualizing Dependencies

```
Dependency Graph for PR #42: "Add rewards multiplier"

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌─────────────────┐         ┌─────────────────────────┐                    │
│  │ orders/         │         │ rewards/calculator.py   │                    │
│  │ processor.py    │         │                         │                    │
│  │                 │   calls │  calculate_rewards()    │                    │
│  │ process_order() │ ───────▶│  [MODIFIED]             │                    │
│  │                 │         │                         │                    │
│  └─────────────────┘         └───────────┬─────────────┘                    │
│                                          │                                   │
│  ┌─────────────────┐                     │ calls                            │
│  │ batch/jobs.py   │                     │                                   │
│  │                 │   calls             ▼                                   │
│  │ daily_rewards() │ ───────▶  ┌─────────────────────┐                      │
│  │                 │           │ users/service.py    │                      │
│  └─────────────────┘           │                     │                      │
│                                │ get_user()          │                      │
│                                │                     │                      │
│  ┌─────────────────┐           └─────────────────────┘                      │
│  │ tests/          │                                                         │
│  │ test_rewards.py │   tests                                                │
│  │                 │ ───────▶  calculate_rewards()                          │
│  │ test_calc_*()   │                                                        │
│  └─────────────────┘                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Identifying Business Logic Impact

```python
# src/analysis/business_impact.py

class BusinessImpactAnalyzer:
    """Analyze business logic impact of changes."""
    
    def analyze_impact(
        self,
        change: FunctionChange,
        callers: list[CallerInfo],
        callees: list[FunctionInfo],
    ) -> BusinessImpact:
        """
        Determine business-level impact of a code change.
        
        Categories:
        - CRITICAL: Payment, auth, data integrity
        - HIGH: Core business logic
        - MEDIUM: Feature functionality
        - LOW: Utility/helper functions
        """
        impact = BusinessImpact(change=change)
        
        # Check function name patterns
        critical_patterns = ['payment', 'auth', 'password', 'encrypt', 'transaction']
        high_patterns = ['order', 'user', 'account', 'billing', 'subscription']
        
        func_name_lower = change.name.lower()
        file_path_lower = change.file_path.lower()
        
        if any(p in func_name_lower or p in file_path_lower for p in critical_patterns):
            impact.level = "CRITICAL"
            impact.reason = f"Function involves {self._match_pattern(func_name_lower, critical_patterns)}"
        elif any(p in func_name_lower or p in file_path_lower for p in high_patterns):
            impact.level = "HIGH"
            impact.reason = f"Function involves core business logic"
        elif len(callers) > 5:
            impact.level = "HIGH"
            impact.reason = f"Function has {len(callers)} callers - wide impact"
        else:
            impact.level = "MEDIUM"
        
        # Add affected areas
        impact.affected_areas = list(set(
            self._classify_area(c.file_path) for c in callers
        ))
        
        return impact
```

---

## Context Assembly Examples

### Example 1: Modified Function

**Scenario**: `calculate_rewards` modified to add `multiplier` parameter

```python
# Context assembled for LLM:

MODIFIED_FUNCTION_CONTEXT = """
## Review Context: Modified Function

### Function: `calculate_rewards`
**File**: rewards/calculator.py
**Change Type**: MODIFIED
**Business Impact**: HIGH (core rewards logic)

---

### BEFORE (from staging_new branch):
```python
def calculate_rewards(user_id: int) -> float:
    '''Calculate rewards for a user based on their points.'''
    user = get_user(user_id)
    return user.points * 0.01
```

### AFTER (from feature/rewards-program branch):
```python
def calculate_rewards(user_id: int, multiplier: float = 1.0) -> float:
    '''Calculate rewards for a user based on their points.
    
    Args:
        user_id: The user's ID
        multiplier: Reward multiplier (default 1.0 for standard rewards)
    
    Returns:
        The calculated reward amount
    '''
    user = get_user(user_id)
    base_reward = user.points * 0.01
    return base_reward * multiplier
```

### DIFF:
```diff
-def calculate_rewards(user_id: int) -> float:
-    '''Calculate rewards for a user based on their points.'''
+def calculate_rewards(user_id: int, multiplier: float = 1.0) -> float:
+    '''Calculate rewards for a user based on their points.
+    
+    Args:
+        user_id: The user's ID
+        multiplier: Reward multiplier (default 1.0 for standard rewards)
+    
+    Returns:
+        The calculated reward amount
+    '''
     user = get_user(user_id)
-    return user.points * 0.01
+    base_reward = user.points * 0.01
+    return base_reward * multiplier
```

---

### CALLERS (functions that call this):

#### 1. orders/processor.py - `process_order` (line 45)
```python
def process_order(order: Order) -> OrderResult:
    # ... previous logic ...
    
    # Calculate rewards for this purchase
    reward = calculate_rewards(order.user_id)  # <-- CALL SITE
    if reward > 0:
        apply_reward(order.user_id, reward)
    
    return OrderResult(success=True, reward_earned=reward)
```
**Note**: Currently not passing multiplier - will use default 1.0

#### 2. batch/jobs.py - `daily_rewards_job` (line 128)
```python
def daily_rewards_job():
    '''Run daily rewards calculation for all active users.'''
    users = get_active_users()
    for user in users:
        reward = calculate_rewards(user.id)  # <-- CALL SITE
        if reward > MIN_REWARD_THRESHOLD:
            queue_reward_notification(user.id, reward)
```
**Note**: Batch job - should this use special multiplier?

---

### CALLEES (functions this calls):

#### 1. users/service.py - `get_user`
```python
def get_user(user_id: int) -> User:
    '''Fetch user from database.'''
    return db.query(User).filter(User.id == user_id).first()
```

---

### TEST COVERAGE:

**Test File**: tests/test_rewards.py
**Existing Tests**:
- `test_calculate_rewards_basic` - Tests with standard user
- `test_calculate_rewards_zero_points` - Tests with 0 points

**Missing Coverage**:
- ❌ No tests for multiplier parameter
- ❌ No tests for multiplier edge cases (0, negative)

---

### REVIEW QUESTIONS:

1. **Backward Compatibility**: The new `multiplier` parameter has a default value of 1.0. 
   - Will all existing callers work correctly?
   - Should any callers be updated to explicitly use the multiplier?

2. **Edge Cases**: What happens if multiplier is:
   - Zero? (Would result in 0 reward)
   - Negative? (Would result in negative reward - probably a bug)
   - Very large? (Could overflow?)

3. **Test Coverage**: 
   - Should new tests be added for the multiplier parameter?
   - What edge cases should be tested?

4. **Business Logic**:
   - Is the docstring update complete and accurate?
   - Should the batch job use a different multiplier than individual orders?
"""
```

### Example 2: New File

**Scenario**: New file `payments/stripe_integration.py`

```python
NEW_FILE_CONTEXT = """
## Review Context: New File

### File: payments/stripe_integration.py
**Status**: ADDED
**Business Impact**: CRITICAL (payment processing)

---

### FILE CONTENT:
```python
'''Stripe payment integration module.'''
from payments.processor import PaymentProcessor, PaymentResult
from core.models import Transaction
from core.config import settings

class StripeIntegration(PaymentProcessor):
    '''Stripe-specific payment implementation.'''
    
    def __init__(self):
        self.api_key = settings.STRIPE_API_KEY
        self.client = stripe.Client(self.api_key)
    
    def process(self, amount: float, currency: str = 'USD') -> PaymentResult:
        '''Process a payment through Stripe.'''
        try:
            charge = self.client.charges.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
            )
            return PaymentResult(success=True, transaction_id=charge.id)
        except stripe.error.CardError as e:
            return PaymentResult(success=False, error=str(e))
```

---

### DEPENDENCIES USED:

#### 1. payments/processor.py - `PaymentProcessor` (base class)
```python
class PaymentProcessor(ABC):
    '''Abstract base class for payment processors.'''
    
    @abstractmethod
    def process(self, amount: float, currency: str) -> PaymentResult:
        '''Process a payment.
        
        Args:
            amount: Payment amount in major currency units
            currency: ISO 4217 currency code
        
        Returns:
            PaymentResult with success status and transaction details
        '''
        pass
```
**Validation**: ✅ Method signature matches base class

#### 2. core/models.py - `Transaction`
```python
class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    amount = Column(Float)
    currency = Column(String(3))
    processor = Column(String(50))
    external_id = Column(String(255))
```
**Note**: Transaction model imported but not used in current code

---

### SIMILAR FILES (potential conflicts):

#### payments/paypal_integration.py
```python
class PayPalIntegration(PaymentProcessor):
    '''PayPal payment implementation.'''
    
    def process(self, amount: float, currency: str = 'USD') -> PaymentResult:
        # Similar structure - follows same pattern ✅
        ...
```
**Comparison**:
- Both inherit from PaymentProcessor ✅
- Both implement process() method ✅
- Both use same return type ✅
- Pattern consistency: GOOD

---

### REVIEW QUESTIONS:

1. **Security**: 
   - Is `settings.STRIPE_API_KEY` properly secured?
   - Should the API key be validated before use?

2. **Error Handling**:
   - Only CardError is caught - what about other Stripe exceptions?
   - Should network errors be handled separately?

3. **Missing Functionality**:
   - Transaction model is imported but never used
   - Should transactions be logged to database?

4. **Pattern Compliance**:
   - Does this follow the same patterns as PayPalIntegration?
   - Is the cents conversion standard across the codebase?
"""
```

---

## Summary

### Context Strategy Principles

1. **Fetch from correct branches**: Always use source and target branches, never main (unless that IS the target)

2. **Be explicit about relationships**: Don't say "related code" - say "functions that call this" or "the base class this inherits from"

3. **Include validation**: Check that function calls match signatures, that imports resolve correctly

4. **Ask specific questions**: Instead of "review this code", ask "is multiplier validated for negative values?"

5. **Show trust levels**: Make it clear what's ground truth vs. inferred

6. **Limit scope**: Better to deeply understand one function than shallowly cover many

"""Tests for CalleeResolver bug fixes."""

import pytest

from src.analysis.ast_analyzer import get_ast_analyzer
from src.analysis.call_graph import CallGraphBuilder
from src.analysis.callee_resolver import CalleeResolver


# Sample Python code for testing
SAMPLE_CODE = '''"""Sample rewards service for testing."""

def get_user_service():
    """Get the user service instance."""
    return UserService()


def process_points_payment(user_id: str, points: int) -> dict:
    """Process a payment with points redemption.
    
    This function demonstrates:
    - Same-file function calls (get_user_service)
    - External function calls (redeem_points, process_payment)
    - Self-reference should be excluded
    """
    user_service = get_user_service()
    
    if points > 0:
        discount = user_service.redeem_points(user_id, points)
        amount = 100.0 - discount
    else:
        amount = 100.0
    
    result = process_payment(user_id, amount)
    return result


def apply_discount(order, discount_percent):
    """Apply a discount to an order."""
    order.discount = discount_percent
    return order
'''


@pytest.mark.asyncio
class TestCalleeResolverFixes:
    """Test that CalleeResolver correctly finds callees after bug fixes."""
    
    async def test_no_self_reference_in_calls(self):
        """Test that functions don't list themselves as callees."""
        analyzer = get_ast_analyzer()
        functions = analyzer.extract_functions("test.py", SAMPLE_CODE)
        
        # Find the process_points_payment function
        target_func = next(f for f in functions if f.name == "process_points_payment")
        
        # Should NOT include self-reference
        assert "process_points_payment" not in target_func.calls, (
            "Function should not list itself as a callee"
        )
    
    async def test_same_file_functions_found(self):
        """Test that same-file function calls are detected."""
        analyzer = get_ast_analyzer()
        functions = analyzer.extract_functions("test.py", SAMPLE_CODE)
        
        target_func = next(f for f in functions if f.name == "process_points_payment")
        
        # Should include same-file function
        assert "get_user_service" in target_func.calls, (
            "Should detect same-file function calls"
        )
    
    async def test_callee_resolver_finds_same_file_functions(self):
        """Test that CalleeResolver can resolve same-file functions."""
        # Build call graph from content
        file_contents = {"test.py": SAMPLE_CODE}
        builder = CallGraphBuilder()
        call_graph = builder.build_from_content(file_contents)
        
        # Get callees for process_points_payment
        callees = call_graph.get_callees("process_points_payment")
        
        # Should include get_user_service
        assert "get_user_service" in callees, (
            f"Expected get_user_service in callees, got: {callees}"
        )
        
        # Should NOT include self
        assert "process_points_payment" not in callees, (
            f"Should not include self-reference, got: {callees}"
        )
    
    async def test_callee_resolver_provides_source_code(self):
        """Test that CalleeResolver provides source code for same-file functions."""
        # Build call graph and file contents
        file_contents = {"test.py": SAMPLE_CODE}
        builder = CallGraphBuilder()
        call_graph = builder.build_from_content(file_contents)
        
        # Resolve callees for process_points_payment
        resolver = CalleeResolver()
        callee_names = call_graph.get_callees("process_points_payment")
        resolved = await resolver.resolve_callees(
            callee_names, call_graph, file_contents
        )
        
        # Should have resolved get_user_service
        get_user_service_info = next(
            (c for c in resolved if c.name == "get_user_service"),
            None
        )
        
        assert get_user_service_info is not None, (
            "Should have resolved get_user_service"
        )
        assert get_user_service_info.source_code is not None, (
            "Should have source code for get_user_service"
        )
        assert get_user_service_info.file_path == "test.py", (
            f"Should have correct file path, got: {get_user_service_info.file_path}"
        )
        assert "return UserService()" in get_user_service_info.source_code, (
            "Source code should contain the actual function body"
        )
    
    async def test_function_definition_not_matched_as_call(self):
        """Test that function definitions are not matched as calls."""
        analyzer = get_ast_analyzer()
        
        # Code with function definition that could be mistakenly matched
        code = '''
def my_function(param1, param2):
    """A function that calls another function."""
    result = other_function(param1)
    return result
'''
        
        functions = analyzer.extract_functions("test.py", code)
        target_func = functions[0]
        
        # Should not include "my_function" in its own calls
        assert "my_function" not in target_func.calls
        
        # Should include actual calls
        assert "other_function" in target_func.calls
    
    async def test_multiple_same_file_callees(self):
        """Test resolving multiple callees from the same file."""
        file_contents = {"test.py": SAMPLE_CODE}
        builder = CallGraphBuilder()
        call_graph = builder.build_from_content(file_contents)
        
        # All functions should be in the call graph
        assert "get_user_service" in call_graph.relations
        assert "process_points_payment" in call_graph.relations
        assert "apply_discount" in call_graph.relations
        
        # Resolve all callees for process_points_payment
        resolver = CalleeResolver()
        callee_names = call_graph.get_callees("process_points_payment")
        resolved = await resolver.resolve_callees(
            callee_names, call_graph, file_contents
        )
        
        # Count how many have source code
        with_source = [c for c in resolved if c.source_code is not None]
        
        # At least get_user_service should be resolved
        assert len(with_source) >= 1, (
            f"Expected at least 1 callee with source code, got {len(with_source)}"
        )
        
        # Verify get_user_service is one of them
        names_with_source = [c.name for c in with_source]
        assert "get_user_service" in names_with_source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

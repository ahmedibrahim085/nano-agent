"""Tests for tool resilience — soft error fallback for unknown tool calls."""

import pytest
from unittest.mock import MagicMock, patch
from agents.tool import FunctionTool
from agents.items import ModelResponse, ToolCallItem, ToolCallOutputItem, Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputText,
    ResponseOutputMessage,
)


class TestToolResilience:
    """Test the pre-filter monkey-patch for unknown tool calls."""

    def _make_function_tool(self, name: str) -> FunctionTool:
        """Helper to create a mock FunctionTool."""
        tool = MagicMock(spec=FunctionTool)
        tool.name = name
        tool.description = f"Mock {name} tool"
        return tool

    def _make_tool_call(self, name: str, call_id: str = "call_1", arguments: str = "{}") -> ResponseFunctionToolCall:
        """Helper to create a ResponseFunctionToolCall."""
        return ResponseFunctionToolCall(
            type="function_call",
            name=name,
            call_id=call_id,
            arguments=arguments,
            status="completed",
        )

    def _make_text_output(self, text: str = "Hello") -> ResponseOutputMessage:
        """Helper to create a text output item wrapped in message."""
        text_content = ResponseOutputText(
            type="output_text",
            text=text,
            annotations=[],
        )
        return ResponseOutputMessage(
            id="msg_1",
            content=[text_content],
            role="assistant",
            status="completed",
            type="message",
        )

    def test_patch_applied_at_import(self):
        """Verify monkey-patch is active after importing nano_agent."""
        from agents.run_internal import turn_resolution as _tr
        # Import nano_agent to trigger the patch
        import nano_agent.modules.nano_agent  # noqa: F401
        # The function should be wrapped (not the original)
        assert hasattr(_tr, 'process_model_response')
        # We can't easily check if it's wrapped without internal markers,
        # but we can verify it's callable
        assert callable(_tr.process_model_response)

    def test_known_tools_unaffected(self):
        """Patch doesn't break normal execution (fast path)."""
        from agents.run_internal import turn_resolution as _tr
        import nano_agent.modules.nano_agent  # noqa: F401

        agent = MagicMock()
        agent.name = "TestAgent"

        # Create a valid tool call
        read_file_tool = self._make_function_tool("read_file")
        tool_call = self._make_tool_call("read_file")

        response = ModelResponse(
            output=[tool_call],
            usage=Usage(),
            response_id="resp_1",
        )

        # This should NOT raise — it goes through the fast path
        result = _tr.process_model_response(
            agent=agent,
            all_tools=[read_file_tool],
            response=response,
            output_schema=None,
            handoffs=[],
        )
        assert result is not None
        assert "read_file" in result.tools_used

    def test_unknown_tool_returns_error_not_crash(self):
        """Unknown tool doesn't raise ModelBehaviorError."""
        from agents.run_internal import turn_resolution as _tr
        import nano_agent.modules.nano_agent  # noqa: F401

        agent = MagicMock()
        agent.name = "TestAgent"

        read_file_tool = self._make_function_tool("read_file")
        unknown_call = self._make_tool_call("run_code_analysis", call_id="call_unknown")

        response = ModelResponse(
            output=[unknown_call],
            usage=Usage(),
            response_id="resp_2",
        )

        # Should NOT raise — the patch handles it gracefully
        result = _tr.process_model_response(
            agent=agent,
            all_tools=[read_file_tool],
            response=response,
            output_schema=None,
            handoffs=[],
        )
        assert result is not None
        # Should have error items for the unknown call
        assert len(result.new_items) >= 1
        # The unknown tool name should appear in tools_used
        assert "run_code_analysis" in result.tools_used

    def test_unknown_tool_error_lists_available_tools(self):
        """Error message contains all available tool names."""
        from agents.run_internal import turn_resolution as _tr
        import nano_agent.modules.nano_agent  # noqa: F401

        agent = MagicMock()
        agent.name = "TestAgent"

        tools = [
            self._make_function_tool("read_file"),
            self._make_function_tool("write_file"),
            self._make_function_tool("bash"),
        ]
        unknown_call = self._make_tool_call("nonexistent_tool")

        response = ModelResponse(
            output=[unknown_call],
            usage=Usage(),
            response_id="resp_3",
        )

        result = _tr.process_model_response(
            agent=agent,
            all_tools=tools,
            response=response,
            output_schema=None,
            handoffs=[],
        )

        # Find the ToolCallOutputItem in new_items
        error_items = [
            item for item in result.new_items
            if isinstance(item, ToolCallOutputItem)
        ]
        assert len(error_items) >= 1
        error_output = error_items[0].output
        assert "read_file" in error_output
        assert "write_file" in error_output
        assert "bash" in error_output

    def test_mixed_valid_and_invalid_calls(self):
        """Valid calls execute normally, invalid get error."""
        from agents.run_internal import turn_resolution as _tr
        import nano_agent.modules.nano_agent  # noqa: F401

        agent = MagicMock()
        agent.name = "TestAgent"

        read_file_tool = self._make_function_tool("read_file")
        valid_call = self._make_tool_call("read_file", call_id="call_valid")
        invalid_call = self._make_tool_call("magic_tool", call_id="call_invalid")

        response = ModelResponse(
            output=[valid_call, invalid_call],
            usage=Usage(),
            response_id="resp_4",
        )

        result = _tr.process_model_response(
            agent=agent,
            all_tools=[read_file_tool],
            response=response,
            output_schema=None,
            handoffs=[],
        )

        assert result is not None
        # Both tool names should be in tools_used
        assert "read_file" in result.tools_used
        assert "magic_tool" in result.tools_used

    def test_multiple_unknown_tools(self):
        """Multiple unknown tools all get error messages."""
        from agents.run_internal import turn_resolution as _tr
        import nano_agent.modules.nano_agent  # noqa: F401

        agent = MagicMock()
        agent.name = "TestAgent"

        tools = [self._make_function_tool("bash")]
        unknown1 = self._make_tool_call("run_tests_magic", call_id="call_u1")
        unknown2 = self._make_tool_call("deploy_app", call_id="call_u2")

        response = ModelResponse(
            output=[unknown1, unknown2],
            usage=Usage(),
            response_id="resp_5",
        )

        result = _tr.process_model_response(
            agent=agent,
            all_tools=tools,
            response=response,
            output_schema=None,
            handoffs=[],
        )

        assert result is not None
        # Both unknown tools should have error items
        error_items = [
            item for item in result.new_items
            if isinstance(item, ToolCallOutputItem)
        ]
        assert len(error_items) >= 2
        assert "run_tests_magic" in result.tools_used
        assert "deploy_app" in result.tools_used

    def test_text_output_preserved_with_unknown_tool(self):
        """Text output items are preserved when unknown tools are filtered."""
        from agents.run_internal import turn_resolution as _tr
        import nano_agent.modules.nano_agent  # noqa: F401

        agent = MagicMock()
        agent.name = "TestAgent"

        tools = [self._make_function_tool("bash")]
        text_item = self._make_text_output("I'll analyze the code")
        unknown_call = self._make_tool_call("analyze_code", call_id="call_x")

        response = ModelResponse(
            output=[text_item, unknown_call],
            usage=Usage(),
            response_id="resp_6",
        )

        result = _tr.process_model_response(
            agent=agent,
            all_tools=tools,
            response=response,
            output_schema=None,
            handoffs=[],
        )

        assert result is not None
        # Should have items for both text and error
        assert len(result.new_items) >= 2

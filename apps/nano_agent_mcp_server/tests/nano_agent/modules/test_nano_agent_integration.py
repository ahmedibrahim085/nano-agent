"""
Integration tests for Nano Agent with OpenAI Agent SDK.

These are real tests that use the smallest available Ollama model and perform
real file operations. No mocking - these tests validate the full agent
execution pipeline.
"""

import pytest
import os
from pathlib import Path
import json

from nano_agent.modules.nano_agent import (
    _execute_nano_agent,
    prompt_nano_agent,
    read_file,
    list_directory,
    write_file,
    get_file_info
)
from nano_agent.modules.nano_agent_tools import set_workspace
from nano_agent.modules.data_types import PromptNanoAgentRequest

from conftest import ollama_available


# Mark all tests as integration tests
pytestmark = pytest.mark.integration


class TestAgentTools:
    """Test the individual agent tools work correctly."""

    @pytest.fixture(autouse=True)
    def _set_workspace(self, tmp_path):
        """Set workspace to tmp_path so file tools accept paths within it."""
        set_workspace(str(tmp_path))

    def test_read_file_tool(self, tmp_path):
        """Test reading a file with the tool."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello from test file!"
        test_file.write_text(test_content)

        result = read_file(str(test_file))
        assert result == test_content

    def test_read_file_not_found(self, tmp_path):
        """Test reading a non-existent file within workspace."""
        result = read_file(str(tmp_path / "nonexistent.txt"))
        assert "Error: File not found" in result

    def test_list_directory_tool(self, tmp_path):
        """Test listing directory contents."""
        # Create some test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "subdir").mkdir()

        result = list_directory(str(tmp_path))

        assert "Total items: 3" in result
        assert "[FILE] file1.txt" in result
        assert "[FILE] file2.py" in result
        assert "[DIR]  subdir/" in result

    def test_write_file_tool(self, tmp_path):
        """Test writing a file."""
        test_file = tmp_path / "output.txt"
        test_content = "Written by agent tool"

        result = write_file(str(test_file), test_content)

        assert "Successfully wrote" in result
        assert test_file.read_text() == test_content

    def test_get_file_info_tool(self, tmp_path):
        """Test getting file information."""
        test_file = tmp_path / "info_test.json"
        test_file.write_text('{"key": "value"}')

        result = get_file_info(str(test_file))
        info = json.loads(result)

        assert info["name"] == "info_test.json"
        assert info["is_file"] is True
        assert info["extension"] == ".json"
        assert info["size_bytes"] == 16


@pytest.mark.skipif(
    not ollama_available(),
    reason="No Ollama models available at 127.0.0.1:11434"
)
class TestNanoAgentIntegration:
    """Integration tests that use the smallest available Ollama model."""

    @pytest.fixture(autouse=True)
    def setup_test_dir(self, tmp_path):
        """Create a test directory for each test."""
        self.test_dir = tmp_path / "agent_test"
        self.test_dir.mkdir()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        yield
        os.chdir(self.original_cwd)

    def test_simple_file_read_task(self, ollama_model):
        """Test agent reading a file."""
        test_file = Path("test_data.txt")
        test_file.write_text("Important data: 42")

        request = PromptNanoAgentRequest(
            agentic_prompt="Read the file test_data.txt and tell me what the important data value is",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert "42" in response.result
        assert response.execution_time_seconds > 0

    def test_list_and_summarize_task(self, ollama_model):
        """Test agent listing directory and summarizing."""
        Path("readme.md").write_text("# Project\nThis is a test project")
        Path("main.py").write_text("def main():\n    print('Hello')")
        Path("config.json").write_text('{"version": "1.0"}')

        request = PromptNanoAgentRequest(
            agentic_prompt="List all files in the current directory and briefly describe what type of project this appears to be",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert any(word in response.result.lower() for word in ["readme", "main.py", "config"])
        assert "turns_used" in response.metadata

    def test_write_file_task(self, ollama_model):
        """Test agent creating a new file."""
        request = PromptNanoAgentRequest(
            agentic_prompt="Create a file called 'hello.txt' with the content 'Hello from nano agent!'",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        hello_file = Path("hello.txt")
        assert hello_file.exists()
        assert hello_file.read_text() == "Hello from nano agent!"

    def test_multi_step_task(self, ollama_model):
        """Test agent performing multiple steps."""
        Path("numbers.txt").write_text("1\n2\n3\n4\n5")

        request = PromptNanoAgentRequest(
            agentic_prompt="""
            1. Read the file numbers.txt
            2. Calculate the sum of all numbers
            3. Create a new file called result.txt with the sum
            """,
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        result_file = Path("result.txt")
        assert result_file.exists()
        content = result_file.read_text()
        assert "15" in content  # Sum of 1+2+3+4+5

    def test_error_handling(self, ollama_model):
        """Test agent handles errors gracefully."""
        request = PromptNanoAgentRequest(
            agentic_prompt="Read a file that doesn't exist: /totally/fake/path/file.txt",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        # Agent should complete (success=True means agent ran, not that file exists)
        assert response.success is True
        # Agent should mention the file issue in some way
        assert response.result is not None
        assert len(response.result) > 0

    def test_file_analysis_task(self, ollama_model):
        """Test agent analyzing file contents."""
        Path("buggy_code.py").write_text("""
def calculate_average(numbers):
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)  # Bug: doesn't handle empty list

def unused_function():
    pass
""")

        request = PromptNanoAgentRequest(
            agentic_prompt="Read buggy_code.py and identify any potential issues or improvements",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert any(word in response.result.lower() for word in ["empty", "zero", "error", "handle"])


@pytest.mark.skipif(
    not ollama_available(),
    reason="No Ollama models available at 127.0.0.1:11434"
)
class TestPromptNanoAgentTool:
    """Test the MCP tool interface with real execution."""

    @pytest.mark.asyncio
    async def test_prompt_nano_agent_simple(self, tmp_path, ollama_model):
        """Test the MCP tool with a simple task."""
        os.chdir(tmp_path)

        result = await prompt_nano_agent(
            agentic_prompt="Create a file called test.txt with the content 'Testing nano agent'",
            model=ollama_model,
            provider="ollama"
        )

        assert result["success"] is True
        assert Path("test.txt").exists()
        assert Path("test.txt").read_text() == "Testing nano agent"

    @pytest.mark.asyncio
    async def test_prompt_nano_agent_with_directory_exploration(self, tmp_path, ollama_model):
        """Test agent exploring directory structure."""
        os.chdir(tmp_path)

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# Main module")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("# Tests")
        (tmp_path / "README.md").write_text("# Project")

        result = await prompt_nano_agent(
            agentic_prompt="Explore the project structure and create a file called 'structure.txt' listing all directories and files",
            model=ollama_model,
            provider="ollama"
        )

        assert result["success"] is True
        assert Path("structure.txt").exists()

        structure_content = Path("structure.txt").read_text()
        assert "src" in structure_content
        assert "tests" in structure_content
        assert "README.md" in structure_content


@pytest.mark.slow
@pytest.mark.skipif(
    not ollama_available(),
    reason="No Ollama models available at 127.0.0.1:11434"
)
class TestPerformance:
    """Performance tests for the nano agent."""

    def test_execution_time(self, tmp_path, ollama_model):
        """Test that simple tasks complete in reasonable time."""
        os.chdir(tmp_path)

        request = PromptNanoAgentRequest(
            agentic_prompt="Create a file called quick.txt with 'Fast test'",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert response.execution_time_seconds < 120  # Local models may be slower

    def test_parallel_tools(self, tmp_path, ollama_model):
        """Test agent can use multiple tools in sequence."""
        os.chdir(tmp_path)

        for i in range(3):
            Path(f"file{i}.txt").write_text(f"Content {i}")

        request = PromptNanoAgentRequest(
            agentic_prompt="Read all txt files and create a summary.txt with their contents",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert response.result is not None

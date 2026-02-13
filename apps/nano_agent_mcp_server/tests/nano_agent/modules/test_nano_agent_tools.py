"""
Tests for Internal Agent Tools.

Tests the tools that the OpenAI Agent SDK agent uses during execution.
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from nano_agent.modules.nano_agent_tools import (
    _read_file_impl,
    _create_file_impl,
    read_file_raw,
    write_file_raw,
    list_files,
    get_file_metadata,
    search_files_raw,
    set_workspace,
    _raw_run_tests,
    _detect_test_framework,
    FRAMEWORK_COMMANDS
)
from nano_agent.modules.data_types import (
    ReadFileRequest,
    ReadFileResponse,
    CreateFileRequest,
    CreateFileResponse
)


class TestReadFileImplementation:
    """Test the internal _read_file_impl function."""
    
    def test_read_file_success(self, tmp_path):
        """Test successful file reading."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        request = ReadFileRequest(
            file_path=str(test_file),
            encoding="utf-8"
        )
        
        response = _read_file_impl(request)
        
        assert response.content == test_content
        assert response.error is None
        assert response.file_size_bytes == len(test_content)
        assert isinstance(response.last_modified, datetime)
    
    def test_read_file_not_found(self):
        """Test reading a non-existent file."""
        request = ReadFileRequest(
            file_path="/non/existent/file.txt",
            encoding="utf-8"
        )
        
        response = _read_file_impl(request)
        
        assert response.content is None
        assert "File not found" in response.error
        assert response.file_size_bytes is None
    
    def test_read_file_directory(self, tmp_path):
        """Test attempting to read a directory."""
        request = ReadFileRequest(
            file_path=str(tmp_path),
            encoding="utf-8"
        )
        
        response = _read_file_impl(request)
        
        assert response.content is None
        assert "not a file" in response.error
    
    def test_read_file_encoding_error(self, tmp_path):
        """Test reading a file with wrong encoding."""
        # Create a file with non-UTF-8 content
        test_file = tmp_path / "binary.dat"
        test_file.write_bytes(b'\x80\x81\x82\x83')
        
        request = ReadFileRequest(
            file_path=str(test_file),
            encoding="utf-8"
        )
        
        response = _read_file_impl(request)
        
        assert response.content is None
        assert "Failed to decode" in response.error
    
    def test_read_file_permission_error(self, tmp_path):
        """Test reading a file without permission."""
        test_file = tmp_path / "restricted.txt"
        test_file.write_text("secret")
        
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            request = ReadFileRequest(
                file_path=str(test_file),
                encoding="utf-8"
            )
            
            response = _read_file_impl(request)
            
            assert response.content is None
            assert "Permission denied" in response.error


class TestCreateFileImplementation:
    """Test the internal _create_file_impl function."""
    
    def test_create_file_success(self, tmp_path):
        """Test successful file creation."""
        test_file = tmp_path / "new_file.txt"
        test_content = "New content"
        
        request = CreateFileRequest(
            file_path=str(test_file),
            content=test_content,
            encoding="utf-8",
            overwrite=False
        )
        
        response = _create_file_impl(request)
        
        assert response.success is True
        assert response.error is None
        assert response.bytes_written == len(test_content)
        assert test_file.read_text() == test_content
    
    def test_create_file_with_directories(self, tmp_path):
        """Test creating a file with non-existent parent directories."""
        test_file = tmp_path / "deep" / "nested" / "dir" / "file.txt"
        test_content = "Deep content"
        
        request = CreateFileRequest(
            file_path=str(test_file),
            content=test_content,
            encoding="utf-8",
            overwrite=False
        )
        
        response = _create_file_impl(request)
        
        assert response.success is True
        assert test_file.exists()
        assert test_file.read_text() == test_content
    
    def test_create_file_exists_no_overwrite(self, tmp_path):
        """Test creating a file that already exists without overwrite."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Original content")
        
        request = CreateFileRequest(
            file_path=str(test_file),
            content="New content",
            encoding="utf-8",
            overwrite=False
        )
        
        response = _create_file_impl(request)
        
        assert response.success is False
        assert "already exists" in response.error
        assert test_file.read_text() == "Original content"  # Unchanged
    
    def test_create_file_exists_with_overwrite(self, tmp_path):
        """Test creating a file that already exists with overwrite."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Original content")
        new_content = "Replaced content"
        
        request = CreateFileRequest(
            file_path=str(test_file),
            content=new_content,
            encoding="utf-8",
            overwrite=True
        )
        
        response = _create_file_impl(request)
        
        assert response.success is True
        assert response.error is None
        assert test_file.read_text() == new_content
    
    def test_create_file_encoding_error(self, tmp_path):
        """Test creating a file with encoding issues."""
        test_file = tmp_path / "encoding_test.txt"
        
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.return_value.write.side_effect = UnicodeEncodeError(
                "ascii", "test", 0, 1, "ordinal not in range"
            )
            
            request = CreateFileRequest(
                file_path=str(test_file),
                content="Test content",
                encoding="ascii",
                overwrite=False
            )
            
            response = _create_file_impl(request)
            
            assert response.success is False
            assert "Failed to encode" in response.error
    
    def test_create_file_permission_error(self, tmp_path):
        """Test creating a file without permission."""
        test_file = tmp_path / "no_permission.txt"
        
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            request = CreateFileRequest(
                file_path=str(test_file),
                content="Test",
                encoding="utf-8",
                overwrite=False
            )
            
            response = _create_file_impl(request)
            
            assert response.success is False
            assert "Permission denied" in response.error


class TestAgentTools:
    """Test the tool functions used by agents."""
    
    def test_read_file_tool(self, tmp_path):
        """Test the read_file tool function."""
        test_file = tmp_path / "agent_test.txt"
        test_content = "Agent readable content"
        test_file.write_text(test_content)
        
        result = read_file_raw(str(test_file))
        
        assert result == test_content
    
    def test_read_file_tool_error(self):
        """Test read_file tool with error."""
        result = read_file_raw("/non/existent/file.txt")
        
        assert "Error: File not found" in result
    
    def test_write_file_tool(self, tmp_path):
        """Test the write_file tool function."""
        test_file = tmp_path / "agent_created.txt"
        test_content = "Content created by agent"
        
        result = write_file_raw(str(test_file), test_content)
        
        assert "Successfully wrote" in result
        assert test_file.read_text() == test_content
    
    def test_write_file_tool_with_overwrite(self, tmp_path):
        """Test write_file tool with overwrite."""
        test_file = tmp_path / "overwrite_test.txt"
        test_file.write_text("Old content")
        new_content = "New content from agent"
        
        result = write_file_raw(str(test_file), new_content)
        
        assert "Successfully wrote" in result
        assert test_file.read_text() == new_content


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_list_files(self, tmp_path):
        """Test listing files in a directory."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.txt").write_text("content3")
        
        # List all files
        files = list_files(str(tmp_path))
        assert len(files) == 2
        assert str(tmp_path / "file1.txt") in files
        assert str(tmp_path / "file2.py") in files
        
        # List with pattern
        txt_files = list_files(str(tmp_path), "*.txt")
        assert len(txt_files) == 1
        assert str(tmp_path / "file1.txt") in txt_files
    
    def test_list_files_non_existent_directory(self):
        """Test listing files in non-existent directory."""
        files = list_files("/non/existent/directory")
        assert files == []
    
    def test_list_files_not_a_directory(self, tmp_path):
        """Test listing files when path is not a directory."""
        test_file = tmp_path / "not_a_dir.txt"
        test_file.write_text("content")
        
        files = list_files(str(test_file))
        assert files == []
    
    def test_get_file_metadata(self, tmp_path):
        """Test getting file metadata."""
        test_file = tmp_path / "info_test.md"
        test_content = "File for info test"
        test_file.write_text(test_content)
        
        info = get_file_metadata(str(test_file))
        
        assert info is not None
        assert info["name"] == "info_test.md"
        assert info["extension"] == ".md"
        assert info["size_bytes"] == len(test_content)
        assert "last_modified" in info
        assert "created" in info
        assert str(test_file.absolute()) == info["path"]
    
    def test_get_file_metadata_non_existent(self):
        """Test getting info for non-existent file."""
        info = get_file_metadata("/non/existent/file.txt")
        assert info is None
    
    def test_get_file_metadata_directory(self, tmp_path):
        """Test getting info for a directory."""
        info = get_file_metadata(str(tmp_path))
        assert info is None


class TestSearchFiles:
    """Test the search_files tool."""

    def test_search_files_basic_pattern(self, tmp_path):
        """Test finding a known string in files."""
        set_workspace(str(tmp_path))
        (tmp_path / "hello.txt").write_text("Hello World\nGoodbye World\n")
        (tmp_path / "other.txt").write_text("Nothing here\n")
        result = search_files_raw("Hello", str(tmp_path))
        assert "hello.txt" in result
        assert "Hello World" in result
        assert "other.txt" not in result

    def test_search_files_regex_pattern(self, tmp_path):
        """Test regex pattern search."""
        set_workspace(str(tmp_path))
        (tmp_path / "code.py").write_text("def foo():\n    return 42\ndef bar():\n    pass\n")
        result = search_files_raw("def [a-z]+\\(\\)", str(tmp_path))
        assert "def foo()" in result
        assert "def bar()" in result

    def test_search_files_with_glob(self, tmp_path):
        """Test file glob filtering."""
        set_workspace(str(tmp_path))
        (tmp_path / "code.py").write_text("pattern_match\n")
        (tmp_path / "readme.txt").write_text("pattern_match\n")
        result = search_files_raw("pattern_match", str(tmp_path), file_glob="*.py")
        assert "code.py" in result
        assert "readme.txt" not in result

    def test_search_files_no_matches(self, tmp_path):
        """Test when no matches found."""
        set_workspace(str(tmp_path))
        (tmp_path / "file.txt").write_text("nothing relevant\n")
        result = search_files_raw("NONEXISTENT_STRING_XYZ", str(tmp_path))
        assert result == "No matches found"

    def test_search_files_nonexistent_directory(self, tmp_path):
        """Test with non-existent directory."""
        set_workspace(str(tmp_path))
        result = search_files_raw("pattern", str(tmp_path / "nonexistent"))
        assert "Error" in result

    def test_search_files_output_truncation(self, tmp_path):
        """Test that large output is truncated."""
        set_workspace(str(tmp_path))
        # Create a file with many matching lines
        content = "\n".join([f"match_line_{i}" for i in range(10000)])
        (tmp_path / "large.txt").write_text(content)
        result = search_files_raw("match_line_", str(tmp_path))
        # Result should be truncated to BASH_OUTPUT_MAX_CHARS
        assert len(result) <= 35000  # some margin above 30000

    def test_search_files_default_directory(self, tmp_path):
        """Test that directory='.' uses workspace."""
        set_workspace(str(tmp_path))
        (tmp_path / "target.txt").write_text("unique_search_term\n")
        result = search_files_raw("unique_search_term")
        assert "target.txt" in result
        assert "unique_search_term" in result


class TestRunTests:
    """Test the run_tests tool."""

    def test_detect_test_framework_pytest_conftest(self, tmp_path):
        """Detect pytest from conftest.py."""
        (tmp_path / "conftest.py").write_text("")
        assert _detect_test_framework(str(tmp_path)) == "pytest"

    def test_detect_test_framework_pytest_pyproject(self, tmp_path):
        """Detect pytest from pyproject.toml with [tool.pytest]."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        assert _detect_test_framework(str(tmp_path)) == "pytest"

    def test_detect_test_framework_npm(self, tmp_path):
        """Detect npm from package.json."""
        (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
        assert _detect_test_framework(str(tmp_path)) == "npm"

    def test_detect_test_framework_cargo(self, tmp_path):
        """Detect cargo from Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        assert _detect_test_framework(str(tmp_path)) == "cargo"

    def test_detect_test_framework_fallback_pytest(self, tmp_path):
        """Fall back to pytest when no markers found."""
        assert _detect_test_framework(str(tmp_path)) == "pytest"

    @pytest.mark.asyncio
    async def test_run_tests_explicit_pytest(self, tmp_path):
        """Run pytest explicitly on a passing test file."""
        set_workspace(str(tmp_path))
        # Create a minimal passing test
        (tmp_path / "test_sample.py").write_text(
            "def test_ok():\n    assert 1 + 1 == 2\n"
        )
        result = await _raw_run_tests(str(tmp_path), "pytest")
        assert "passed" in result.lower() or "1 passed" in result

    @pytest.mark.asyncio
    async def test_run_tests_test_failure(self, tmp_path):
        """Test failure output is returned (not raised as error)."""
        set_workspace(str(tmp_path))
        (tmp_path / "test_fail.py").write_text(
            "def test_bad():\n    assert False\n"
        )
        result = await _raw_run_tests(str(tmp_path), "pytest")
        # Should contain failure info, NOT be an error string
        assert "failed" in result.lower() or "FAILED" in result

    @pytest.mark.asyncio
    async def test_run_tests_auto_detect_pytest(self, tmp_path):
        """Auto-detect pytest and run."""
        set_workspace(str(tmp_path))
        (tmp_path / "conftest.py").write_text("")
        (tmp_path / "test_auto.py").write_text(
            "def test_auto():\n    assert True\n"
        )
        result = await _raw_run_tests(str(tmp_path), "auto")
        assert "passed" in result.lower()
"""
Internal Agent Tools for Nano Agent.

This module contains tools that the OpenAI Agent SDK agent will use
to complete its work. These are not exposed directly via MCP but are
available to the agent during execution.
"""

import asyncio
import os
import logging
import contextvars
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Import function_tool decorator from agents SDK
try:
    from agents import function_tool
except ImportError:
    # Fallback if agents SDK not available
    def function_tool(func):
        return func

from .data_types import (
    ReadFileRequest,
    ReadFileResponse,
    CreateFileRequest,
    CreateFileResponse
)
from .constants import (
    ERROR_FILE_NOT_FOUND,
    ERROR_NOT_A_FILE,
    ERROR_DIR_NOT_FOUND,
    ERROR_NOT_A_DIR,
    SUCCESS_FILE_WRITE,
    SUCCESS_FILE_EDIT
)
from .files import (
    resolve_path,
    get_working_directory,
    ensure_parent_exists,
    format_path_for_display
)

# Initialize logger
logger = logging.getLogger(__name__)


def _read_file_impl(request: ReadFileRequest) -> ReadFileResponse:
    """
    Internal implementation of read_file tool.
    
    Isolated for testing and reusability.
    
    Args:
        request: Validated request with file path and encoding
        
    Returns:
        Response with file content or error information
    """
    try:
        # Resolve to absolute path
        file_path = resolve_path(request.file_path)
        
        # Check if file exists
        if not file_path.exists():
            logger.warning(f"File not found: {request.file_path}")
            return ReadFileResponse(
                error=f"File not found: {request.file_path}"
            )
        
        # Check if it's a file (not directory)
        if not file_path.is_file():
            logger.warning(f"Path is not a file: {request.file_path}")
            return ReadFileResponse(
                error=f"Path is not a file: {request.file_path}"
            )
        
        # Get file metadata
        stat = file_path.stat()
        file_size = stat.st_size
        last_modified = datetime.fromtimestamp(stat.st_mtime)
        
        # Read file content
        try:
            with open(file_path, 'r', encoding=request.encoding) as f:
                content = f.read()
                
            logger.info(f"Successfully read file: {request.file_path} ({file_size} bytes)")
            
            return ReadFileResponse(
                content=content,
                file_size_bytes=file_size,
                last_modified=last_modified
            )
            
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {request.file_path}: {e}")
            return ReadFileResponse(
                error=f"Failed to decode file with {request.encoding} encoding: {str(e)}"
            )
            
    except PermissionError as e:
        logger.error(f"Permission denied reading {request.file_path}: {e}")
        return ReadFileResponse(
            error=f"Permission denied: {request.file_path}"
        )
    except Exception as e:
        logger.error(f"Unexpected error reading {request.file_path}: {e}", exc_info=True)
        return ReadFileResponse(
            error=f"Unexpected error: {str(e)}"
        )


def _create_file_impl(request: CreateFileRequest) -> CreateFileResponse:
    """
    Internal implementation of create_file tool.
    
    Isolated for testing and reusability.
    
    Args:
        request: Validated request with file path, content, and options
        
    Returns:
        Response with success status or error information
    """
    try:
        # Resolve to absolute path
        file_path = resolve_path(request.file_path)
        
        # Check if file exists and overwrite is not allowed
        if file_path.exists() and not request.overwrite:
            logger.warning(f"File exists and overwrite=False: {request.file_path}")
            return CreateFileResponse(
                success=False,
                file_path=request.file_path,
                error=f"File already exists: {request.file_path}. Set overwrite=True to replace."
            )
        
        # Create parent directories if they don't exist
        ensure_parent_exists(file_path)
        
        # Write file content
        try:
            with open(file_path, 'w', encoding=request.encoding) as f:
                f.write(request.content)
                bytes_written = f.tell()
            
            logger.info(f"Successfully created file: {request.file_path} ({bytes_written} bytes)")
            
            return CreateFileResponse(
                success=True,
                file_path=str(file_path.absolute()),
                bytes_written=bytes_written
            )
            
        except UnicodeEncodeError as e:
            logger.error(f"Encoding error writing {request.file_path}: {e}")
            return CreateFileResponse(
                success=False,
                file_path=request.file_path,
                error=f"Failed to encode content with {request.encoding} encoding: {str(e)}"
            )
            
    except PermissionError as e:
        logger.error(f"Permission denied writing {request.file_path}: {e}")
        return CreateFileResponse(
            success=False,
            file_path=request.file_path,
            error=f"Permission denied: {request.file_path}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating {request.file_path}: {e}", exc_info=True)
        return CreateFileResponse(
            success=False,
            file_path=request.file_path,
            error=f"Unexpected error: {str(e)}"
        )


# Raw tool implementations (not decorated)
def read_file_raw(file_path: str) -> str:
    """
    Read the contents of a file.
    
    Args:
        file_path: Path to the file to read (relative or absolute)
    
    Returns:
        File contents as string, or error message if failed
    """
    try:
        # Resolve to absolute path
        path = resolve_path(file_path)
        
        if not path.exists():
            return ERROR_FILE_NOT_FOUND.format(file_path)
        if not path.is_file():
            return ERROR_NOT_A_FILE.format(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Log with both display path and absolute path for clarity
        display_path = format_path_for_display(path)
        logger.info(f"Successfully read file: {display_path} ({len(content)} chars) [absolute: {path}]")
        return content
    except Exception as e:
        error_msg = f"Error reading file {file_path}: {str(e)}"
        logger.error(error_msg)
        return error_msg


def write_file_raw(file_path: str, content: str) -> str:
    """
    Write content to a file.
    
    Args:
        file_path: Path where the file should be written (relative or absolute)
        content: Content to write to the file
    
    Returns:
        Success message or error
    """
    try:
        # Resolve to absolute path
        path = resolve_path(file_path)
        
        # Ensure parent directories exist
        ensure_parent_exists(path)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        size = len(content)
        display_path = format_path_for_display(path)
        logger.info(f"Successfully wrote file: {display_path} ({size} bytes) [absolute: {path}]")
        return SUCCESS_FILE_WRITE.format(size, display_path)
    except Exception as e:
        error_msg = f"Error writing file {file_path}: {str(e)}"
        logger.error(error_msg)
        return error_msg


def list_directory_raw(directory_path: Optional[str] = None) -> str:
    """
    List contents of a directory.
    
    Args:
        directory_path: Path to directory (default: current working directory)
    
    Returns:
        Formatted directory listing or error message
    """
    try:
        # Default to current working directory if no path provided
        if directory_path is None:
            path = get_working_directory()
        else:
            # Resolve to absolute path
            path = resolve_path(directory_path)
        
        if not path.exists():
            dir_display = directory_path if directory_path else str(path)
            return ERROR_DIR_NOT_FOUND.format(dir_display)
        if not path.is_dir():
            dir_display = directory_path if directory_path else str(path)
            return ERROR_NOT_A_DIR.format(dir_display)
        
        items = []
        for item in sorted(path.iterdir()):
            if item.is_dir():
                items.append(f"[DIR]  {item.name}/")
            else:
                size = item.stat().st_size
                items.append(f"[FILE] {item.name} ({size} bytes)")
        
        # When no directory_path was provided, show absolute path
        if directory_path is None:
            display_path = str(path)  # Show absolute path
        else:
            display_path = format_path_for_display(path)
        result = f"Directory: {display_path}\n"
        result += f"Total items: {len(items)}\n"
        result += "\n".join(items) if items else "Empty directory"
        
        logger.info(f"Listed directory: {display_path} ({len(items)} items) [absolute: {path}]")
        return result
    except Exception as e:
        error_msg = f"Error listing directory {directory_path}: {str(e)}"
        logger.error(error_msg)
        return error_msg

def edit_file_raw(file_path: str, old_str: str, new_str: str) -> str:
    """
    Edit a file by replacing exact text matches.
    
    Args:
        file_path: Path to the file to edit (relative or absolute)
        old_str: The exact text to find and replace (must match exactly including whitespace)
        new_str: The new text to insert in place of old_str
    
    Returns:
        Success message or detailed error message
    """
    try:
        # Resolve to absolute path
        path = resolve_path(file_path)
        
        # Check if file exists
        if not path.exists():
            return f"Error: File not found: {file_path}"
        
        # Check if it's a file (not directory)
        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"
        
        # Read the current content
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as e:
            return f"Error: Cannot read file (encoding issue): {str(e)}"
        
        # Check if old_str exists in the file
        if old_str not in content:
            # Provide helpful feedback
            lines = old_str.split('\n')
            if len(lines) > 1:
                # Multi-line search - check if any lines exist
                found_lines = []
                for line in lines:
                    if line.strip() and line.strip() in content:
                        found_lines.append(line.strip())
                
                if found_lines:
                    return (f"Error: Exact text not found in file. "
                           f"Found similar lines but not exact match. "
                           f"Check whitespace and indentation. "
                           f"Found: {found_lines[:3]}")  # Show first 3 matches
                else:
                    return f"Error: Text not found in file. None of the lines exist in the file."
            else:
                # Single line search - provide more context
                stripped = old_str.strip()
                if stripped and stripped in content:
                    return (f"Error: Found similar text but not exact match. "
                           f"Check whitespace and indentation around: '{stripped[:50]}...'")
                else:
                    return f"Error: Text not found in file: '{old_str[:100]}...'"
        
        # Check for multiple occurrences
        occurrences = content.count(old_str)
        if occurrences > 1:
            return (f"Error: Found {occurrences} occurrences of the text. "
                   f"Please provide more context to make the match unique, "
                   f"or use a different tool to replace all occurrences.")
        
        # Perform the replacement
        new_content = content.replace(old_str, new_str, 1)  # Replace only first occurrence
        
        # Write the updated content back
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return f"Error: Failed to write file: {str(e)}"
        
        # Log the operation
        display_path = format_path_for_display(path)
        logger.info(f"Successfully edited file: {display_path} [absolute: {path}]")
        
        return SUCCESS_FILE_EDIT
        
    except PermissionError:
        return f"Error: Permission denied when accessing file: {file_path}"
    except Exception as e:
        error_msg = f"Error editing file {file_path}: {str(e)}"
        logger.error(error_msg)
        return error_msg


def get_file_info_raw(file_path: str) -> str:
    """
    Get detailed information about a file.
    
    Args:
        file_path: Path to the file (relative or absolute)
    
    Returns:
        JSON string with file information or error message
    """
    try:
        # Resolve to absolute path
        path = resolve_path(file_path)
        
        if not path.exists():
            return ERROR_FILE_NOT_FOUND.format(file_path)
        
        stat = path.stat()
        display_path = format_path_for_display(path)
        
        info = {
            "path": display_path,
            "absolute_path": str(path),
            "name": path.name,
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
            "size_bytes": stat.st_size if path.is_file() else None,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": path.suffix if path.is_file() else None,
        }
        
        logger.info(f"Got file info for: {display_path} [absolute: {path}]")
        return json.dumps(info, indent=2)
    except Exception as e:
        error_msg = f"Error getting file info for {file_path}: {str(e)}"
        logger.error(error_msg)
        return error_msg

# Additional utility functions

def list_files(directory: str, pattern: str = "*") -> list[str]:
    """
    List files in a directory matching a pattern.
    
    This is a utility function that might be useful for agents.
    
    Args:
        directory: Directory path to list (relative or absolute)
        pattern: Glob pattern to match (default: "*" for all files)
        
    Returns:
        List of file paths matching the pattern (as display paths)
    """
    try:
        # Resolve to absolute path
        dir_path = resolve_path(directory)
        
        if not dir_path.is_dir():
            return []
        
        files = []
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                # Return display paths for cleaner output
                files.append(format_path_for_display(file_path))
        
        return sorted(files)
    except Exception as e:
        logger.error(f"Error listing files in {directory}: {e}")
        return []


def get_file_metadata(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata about a file without reading its content.
    Utility function, not exposed as a tool.
    
    Args:
        file_path: Path to the file (relative or absolute)
        
    Returns:
        Dictionary with file metadata or None if file doesn't exist
    """
    try:
        # Resolve to absolute path
        path = resolve_path(file_path)
        
        if not path.exists() or not path.is_file():
            return None
        
        stat = path.stat()
        display_path = format_path_for_display(path)
        
        return {
            "path": display_path,
            "absolute_path": str(path),
            "size_bytes": stat.st_size,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "extension": path.suffix,
            "name": path.name
        }
    except Exception as e:
        logger.error(f"Error getting file metadata for {file_path}: {e}")
        return None


# Workspace directory for agent operations (set per-invocation)
# Using ContextVar for async-safe per-task isolation
_workspace_dir_var: contextvars.ContextVar[Optional[Path]] = contextvars.ContextVar(
    '_workspace_dir', default=None
)

# Tool call arguments storage (for lifecycle hook access)
# Using ContextVar for async-safe per-task isolation
_last_tool_args_var: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    '_last_tool_args', default=None
)
_pending_tool_args_var: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    '_pending_tool_args', default=None
)

COMMAND_TIMEOUT_SECONDS = 120

# Bash tool output limits (matches Claude Code's Bash tool)
BASH_OUTPUT_MAX_CHARS = 30000
BASH_OUTPUT_HEAD_RATIO = 0.6   # Keep 60% from start
BASH_OUTPUT_TAIL_RATIO = 0.35  # Keep 35% from end

# CWD tracking marker — unique enough to avoid collisions with user output
_CWD_MARKER = "__NANO_CWD_f7e2a1__"

# Persistent CWD for bash tool (per-task via ContextVar)
_bash_cwd_var: contextvars.ContextVar[Optional[Path]] = contextvars.ContextVar(
    '_bash_cwd', default=None
)


def set_workspace(workspace: Optional[str] = None) -> Path:
    """Set the workspace directory for agent tools.

    Args:
        workspace: Directory path. If None, uses cwd.

    Returns:
        The resolved workspace Path.
    """
    if workspace:
        ws = Path(workspace).resolve()
    else:
        ws = Path.cwd()
    ws.mkdir(parents=True, exist_ok=True)
    _workspace_dir_var.set(ws)
    _bash_cwd_var.set(None)  # Reset CWD tracking for new session
    return ws


def get_workspace() -> Path:
    """Get the current workspace directory."""
    ws = _workspace_dir_var.get()
    if ws is None:
        return Path.cwd()
    return ws


def get_bash_cwd() -> Path:
    """Get CWD for bash tool — persists across calls within a session."""
    cwd = _bash_cwd_var.get()
    return cwd if cwd is not None else get_workspace()


def _parse_cwd_from_output(stdout: str) -> tuple[str, Optional[Path]]:
    """Extract CWD from marker in stdout. Returns (clean_output, new_cwd)."""
    marker_idx = stdout.rfind(_CWD_MARKER)  # LAST occurrence
    if marker_idx == -1:
        return stdout, None
    clean_output = stdout[:marker_idx].rstrip()
    after_marker = stdout[marker_idx + len(_CWD_MARKER):].strip()
    cwd_line = after_marker.split('\n')[0].strip()
    if cwd_line and Path(cwd_line).is_absolute():
        return clean_output, Path(cwd_line)
    return clean_output, None


def capture_args(tool_name: str, **kwargs):
    """Capture tool arguments for lifecycle hooks."""
    # Get or create the dicts for this context
    last = _last_tool_args_var.get()
    if last is None:
        last = {}
        _last_tool_args_var.set(last)

    pending = _pending_tool_args_var.get()
    if pending is None:
        pending = {}
        _pending_tool_args_var.set(pending)

    last[tool_name] = kwargs
    pending[tool_name] = kwargs
    logger.debug(f"Captured args for {tool_name}: {kwargs}")

# Decorated tool functions for OpenAI Agent SDK
@function_tool
def read_file(file_path: str) -> str:
    """Read the contents of a file."""
    capture_args("read_file", file_path=file_path)
    return read_file_raw(file_path)

@function_tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file."""
    capture_args("write_file", file_path=file_path, content=content)
    return write_file_raw(file_path, content)

@function_tool
def list_directory(directory_path: Optional[str] = None) -> str:
    """List contents of a directory (defaults to current working directory)."""
    if directory_path is not None:
        capture_args("list_directory", directory_path=directory_path)
    else:
        capture_args("list_directory", directory_path="<current working directory>")
    return list_directory_raw(directory_path)

@function_tool
def get_file_info(file_path: str) -> str:
    """Get detailed information about a file."""
    capture_args("get_file_info", file_path=file_path)
    return get_file_info_raw(file_path)

@function_tool
def edit_file(file_path: str, old_str: str, new_str: str) -> str:
    """Edit a file by replacing exact text with new text.

    IMPORTANT: This tool performs exact string matching including all whitespace and indentation.

    Args:
        file_path: The path to the file to modify (relative or absolute)
        old_str: The exact text to find and replace. Must match EXACTLY including:
                - All spaces and tabs
                - Line breaks
                - Indentation
                Use the read_file tool first to get the exact text format.
        new_str: The new text to insert in place of old_str

    Returns:
        'Successfully updated file' on success, or a detailed error message explaining:
        - If the file doesn't exist
        - If the old_str wasn't found (with hints about similar text)
        - If multiple matches were found (asks for more context)
        - Any permission or encoding issues

    Example usage:
        1. First read the file to see exact formatting:
           read_file('config.py')
        2. Then edit with exact match:
           edit_file('config.py', 'DEBUG = False', 'DEBUG = True')

    Common issues:
        - Spaces vs tabs: The text must match exactly
        - Line endings: Include \n if matching multiple lines
        - Hidden whitespace: Copy exactly from read_file output
    """
    capture_args("edit_file", file_path=file_path, old_str=old_str, new_str=new_str)
    return edit_file_raw(file_path, old_str, new_str)


@function_tool
async def bash(command: str) -> str:
    """Execute shell commands, scripts, and multi-command pipelines in the workspace.

    Supports chained commands (&&, ;, |), scripts, and persistent CWD across calls.
    If you run 'cd /some/dir', subsequent bash calls will start in that directory.

    Args:
        command: Shell command(s) to execute (e.g. "npm install && npm test",
                 "cd src && python -m pytest", "grep -r TODO . | wc -l")

    Returns:
        Combined stdout/stderr and exit code, or an error message on failure/timeout.
    """
    capture_args("bash", command=command)
    cwd = get_bash_cwd()

    if not cwd.exists():
        return f"Error: Workspace directory does not exist: {cwd}"

    # Wrap command to capture CWD after execution (for persistent CWD tracking)
    wrapped = (
        f'{command}; __nano_exit=$?; '
        f'echo "{_CWD_MARKER}"; pwd; '
        f'exit $__nano_exit'
    )

    try:
        proc = await asyncio.create_subprocess_shell(
            wrapped,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"Error: Command timed out after {COMMAND_TIMEOUT_SECONDS}s: {command}"

        stdout_raw = stdout_bytes.decode("utf-8", errors="ignore")
        stderr = stderr_bytes.decode("utf-8", errors="ignore")

        # Parse CWD from stdout and strip the marker
        stdout_clean, new_cwd = _parse_cwd_from_output(stdout_raw)
        if new_cwd is not None:
            _bash_cwd_var.set(new_cwd)

        parts = []
        if stdout_clean.strip():
            parts.append(stdout_clean.strip())
        if stderr.strip():
            parts.append(f"stderr:\n{stderr.strip()}")
        parts.append(f"[exit_code: {proc.returncode}]")

        result = "\n".join(parts)
        # Truncate very long output to stay within token budget
        if len(result) > BASH_OUTPUT_MAX_CHARS:
            head = int(BASH_OUTPUT_MAX_CHARS * BASH_OUTPUT_HEAD_RATIO)
            tail = int(BASH_OUTPUT_MAX_CHARS * BASH_OUTPUT_TAIL_RATIO)
            result = result[:head] + "\n...(truncated)...\n" + result[-tail:]
        return result

    except Exception as e:
        return f"Error executing command: {str(e)}"


# Export all tools for the agent
def get_nano_agent_tools():
    """
    Get all tools for the nano agent.
    
    Returns:
        List of tool functions decorated with @function_tool
    """
    return [
        read_file,
        write_file,
        list_directory,
        get_file_info,
        edit_file,
        bash,
    ]
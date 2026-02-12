"""
Data types for Nano Agent MCP Server.

All request/response models using Pydantic for validation and type safety.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, List
from datetime import datetime


# MCP Tool Request/Response Models

class PromptNanoAgentRequest(BaseModel):
    """Request model for prompt_nano_agent MCP tool."""
    agentic_prompt: str = Field(
        ...,
        description="Natural language description of the work to be done",
        min_length=1,
        max_length=10000
    )
    model: str = Field(
        default="gpt-5-mini",
        description="LLM model to use for the agent"
    )
    provider: Literal["openai", "anthropic", "ollama", "lmstudio", "zai", "qwen"] = Field(
        default="openai",
        description="LLM provider for the agent"
    )
    workspace: Optional[str] = Field(
        default=None,
        description="Working directory for the agent. Shell commands run here. Defaults to cwd."
    )


class LaunchAgentRequest(BaseModel):
    """Request model for launch_agent MCP tool.

    Deploys an agent with a specific identity (from agent_path/AGENT.md)
    to work on a project (in workspace directory).
    """
    agentic_prompt: str = Field(
        ...,
        description="Natural language description of the work to be done",
        min_length=1,
        max_length=10000
    )
    agent_path: str = Field(
        ...,
        description="Path to directory containing the agent's AGENT.md identity file",
        min_length=1
    )
    model: str = Field(
        default="gpt-5-mini",
        description="LLM model to use for the agent"
    )
    provider: Literal["openai", "anthropic", "ollama", "lmstudio", "zai", "qwen"] = Field(
        default="openai",
        description="LLM provider for the agent"
    )
    workspace: Optional[str] = Field(
        default=None,
        description="Working directory for the agent. Shell commands run here. Defaults to cwd."
    )


class PromptNanoAgentResponse(BaseModel):
    """Response model for prompt_nano_agent MCP tool."""
    success: bool = Field(description="Whether the agent completed successfully")
    result: Optional[str] = Field(default=None, description="Agent execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata"
    )
    execution_time_seconds: Optional[float] = Field(
        default=None,
        description="Total execution time"
    )


class ProviderHealthStatus(BaseModel):
    """Health status for a single provider."""
    status: Literal["up", "down", "partial"] = Field(
        description="Provider health status"
    )
    available_models: List[str] = Field(
        default_factory=list,
        description="List of available model names"
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Response latency in milliseconds"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if status is 'down'"
    )


class ModelCapability(BaseModel):
    """Per-model capability and settings configuration."""
    temperature: float = Field(
        default=0.2,
        ge=0.0, le=2.0,
        description="Default temperature for this model"
    )
    max_tokens: int = Field(
        default=16000,
        gt=0,
        description="Maximum output tokens for this model"
    )
    supports_tools: bool = Field(
        default=True,
        description="Whether this model supports function/tool calling"
    )
    supports_temperature: bool = Field(
        default=True,
        description="Whether this model accepts temperature parameter"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Top-p sampling (None = use model default)"
    )


class CheckProvidersResponse(BaseModel):
    """Response model for check_providers MCP tool."""
    success: bool = Field(description="Whether health checks completed successfully")
    providers: Dict[str, ProviderHealthStatus] = Field(
        description="Health status per provider"
    )
    total_check_time_ms: float = Field(
        description="Total time for all checks in milliseconds"
    )
    providers_up: int = Field(
        default=0,
        description="Count of providers with status='up'"
    )
    providers_down: int = Field(
        default=0,
        description="Count of providers with status='down'"
    )
    providers_partial: int = Field(
        default=0,
        description="Count of providers with status='partial'"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if health check itself failed"
    )


# Internal Agent Tool Models

class ReadFileRequest(BaseModel):
    """Request model for read_file agent tool."""
    file_path: str = Field(
        ...,
        description="Path to the file to read",
        min_length=1
    )
    encoding: str = Field(
        default="utf-8",
        description="File encoding"
    )


class ReadFileResponse(BaseModel):
    """Response model for read_file agent tool."""
    content: Optional[str] = Field(default=None, description="File contents")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    file_size_bytes: Optional[int] = Field(default=None, description="File size")
    last_modified: Optional[datetime] = Field(default=None, description="Last modification time")


class CreateFileRequest(BaseModel):
    """Request model for create_file agent tool."""
    file_path: str = Field(
        ...,
        description="Path where the file should be created",
        min_length=1
    )
    content: str = Field(
        ...,
        description="Content to write to the file"
    )
    encoding: str = Field(
        default="utf-8",
        description="File encoding"
    )
    overwrite: bool = Field(
        default=False,
        description="Whether to overwrite if file exists"
    )


class CreateFileResponse(BaseModel):
    """Response model for create_file agent tool."""
    success: bool = Field(description="Whether file was created successfully")
    file_path: str = Field(description="Path to the created file")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    bytes_written: Optional[int] = Field(default=None, description="Number of bytes written")


# Agent Configuration Models

class AgentConfig(BaseModel):
    """Configuration for the nano agent."""
    model: str = Field(description="LLM model identifier")
    provider: Literal["openai", "anthropic", "ollama", "lmstudio", "zai", "qwen"] = Field(description="LLM provider")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=4000,
        gt=0,
        description="Maximum tokens in response"
    )
    timeout_seconds: int = Field(
        default=300,
        gt=0,
        description="Execution timeout"
    )


# Execution Tracking Models

class ToolCall(BaseModel):
    """Record of a single tool call."""
    tool_name: str = Field(description="Name of the tool called")
    arguments: Dict[str, Any] = Field(description="Arguments passed to the tool")
    result: Optional[Any] = Field(default=None, description="Tool execution result")
    error: Optional[str] = Field(default=None, description="Error if tool failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the tool was called")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration")


class AgentExecution(BaseModel):
    """Complete record of an agent execution."""
    prompt: str = Field(description="Original prompt")
    config: AgentConfig = Field(description="Agent configuration used")
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="All tool calls made during execution"
    )
    final_result: Optional[str] = Field(default=None, description="Final execution result")
    total_tokens_used: Optional[int] = Field(default=None, description="Total tokens consumed")
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)
    success: bool = Field(default=False, description="Whether execution completed successfully")
    error: Optional[str] = Field(default=None, description="Error message if failed")
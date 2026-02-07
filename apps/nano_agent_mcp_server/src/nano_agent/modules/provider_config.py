"""
Provider Configuration for Multi-Model Support.

This module provides a thin abstraction layer for creating agents
with different model providers (OpenAI, Anthropic, Ollama).
"""

from typing import Optional, Union
import os
import logging
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, ModelSettings, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel
import requests

# Apply typing fixes for Python 3.12+ compatibility
from . import typing_fix

logger = logging.getLogger(__name__)


class ProviderConfig:
    """Configuration for different model providers."""
    
    @staticmethod
    def get_model_settings(model: str, provider: str, base_settings: dict) -> ModelSettings:
        """Get appropriate model settings for a given model and provider.
        
        Args:
            model: Model identifier
            provider: Provider name
            base_settings: Base settings dictionary with temperature, max_tokens, etc.
            
        Returns:
            ModelSettings configured appropriately for the model
        """
        # Filter settings based on model capabilities
        filtered_settings = {}
        
        # GPT-5 models have special requirements
        if model.startswith("gpt-5"):
            logger.debug(f"Configuring GPT-5 model {model} - using max_completion_tokens")
            # GPT-5 uses max_completion_tokens instead of max_tokens
            if "max_tokens" in base_settings:
                filtered_settings["max_completion_tokens"] = base_settings["max_tokens"]
            # GPT-5 models only support temperature=1 (default)
            # Don't include temperature in settings
        else:
            # Other models support all settings
            filtered_settings = base_settings.copy()
        
        # Anthropic models use the same parameters via OpenAI-compatible endpoint
        if provider == "anthropic":
            pass
        
        logger.debug(f"Model settings for {model}: {filtered_settings}")
        return ModelSettings(**filtered_settings)
    
    @staticmethod
    def create_agent(
        name: str,
        instructions: str,
        tools: list,
        model: str,
        provider: str,
        model_settings: Optional[ModelSettings] = None
    ) -> Agent:
        """Create an agent with the appropriate provider configuration.
        
        Args:
            name: Agent name
            instructions: System instructions for the agent
            tools: List of tool functions
            model: Model identifier
            provider: Provider name ('openai', 'anthropic', 'ollama')
            model_settings: Optional model settings
            
        Returns:
            Configured Agent instance
            
        Raises:
            ValueError: If provider is not supported
        """
        
        if provider == "openai":
            # Default OpenAI configuration
            logger.debug(f"Creating OpenAI agent with model: {model}")
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=model,
                model_settings=model_settings
            )
        
        elif provider == "anthropic":
            # Use OpenAI SDK with Anthropic's OpenAI-compatible endpoint
            logger.debug(f"Creating Anthropic agent with model: {model}")
            anthropic_client = AsyncOpenAI(
                base_url="https://api.anthropic.com/v1/",
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=anthropic_client
                ),
                model_settings=model_settings
            )
        
        elif provider == "ollama":
            # Use OpenAI-compatible endpoint for Ollama
            logger.debug(f"Creating Ollama agent with model: {model}")
            ollama_client = AsyncOpenAI(
                base_url="http://127.0.0.1:11434/v1",
                api_key="ollama"  # Dummy key required by client
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=ollama_client
                ),
                model_settings=model_settings
            )

        elif provider == "lmstudio":
            # Use OpenAI-compatible endpoint for LM Studio
            logger.debug(f"Creating LM Studio agent with model: {model}")
            lmstudio_client = AsyncOpenAI(
                base_url="http://127.0.0.1:1234/v1",
                api_key="lm-studio"  # Dummy key required by client
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=lmstudio_client
                ),
                model_settings=model_settings
            )

        elif provider == "zai":
            # Z.ai uses Anthropic-compatible API — route via LiteLLM
            from .constants import ZAI_BASE_URL
            logger.debug(f"Creating Z.ai agent with model: {model}")
            zai_model = LitellmModel(
                model=f"anthropic/{model}",
                base_url=ZAI_BASE_URL,
                api_key=os.getenv("Z_AI_API_KEY")
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=zai_model,
                model_settings=model_settings
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    @staticmethod
    def setup_provider(provider: str) -> None:
        """Setup provider-specific configurations.
        
        Args:
            provider: Provider name
        """
        if provider != "openai":
            # Always disable OpenAI tracing/telemetry for non-OpenAI providers
            # No need to send telemetry to OpenAI when using Ollama or Anthropic
            logger.info(f"Disabling OpenAI tracing for {provider} provider")
            set_tracing_disabled(True)
    
    @staticmethod
    def validate_provider_setup(provider: str, model: str, available_models: dict, provider_requirements: dict) -> tuple[bool, Optional[str]]:
        """Validate that provider is properly configured.
        
        Args:
            provider: Provider name
            model: Model identifier
            available_models: Dictionary of available models per provider
            provider_requirements: Dictionary of API key requirements
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        
        # Local providers: dynamically validate against the running service
        local_providers = {
            "ollama": ("http://127.0.0.1:11434", "/api/tags", lambda d: [m["name"] for m in d.get("models", [])], "ollama serve"),
            "lmstudio": ("http://127.0.0.1:1234", "/v1/models", lambda d: [m["id"] for m in d.get("data", [])], "LM Studio app"),
        }

        # Z.ai: validate against known model list
        if provider == "zai":
            from .constants import ZAI_AVAILABLE_MODELS
            if model not in ZAI_AVAILABLE_MODELS:
                return False, f"Model '{model}' not available for Z.ai. Available: {', '.join(ZAI_AVAILABLE_MODELS)}"
            required_key = provider_requirements.get(provider)
            if required_key and not os.getenv(required_key):
                return False, f"Missing environment variable: {required_key}"
            return True, None

        if provider in local_providers:
            base_url, endpoint, extract_models, start_hint = local_providers[provider]
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=3)
                models = extract_models(response.json())
                if model not in models:
                    available = ", ".join(models[:10])
                    hint = f" (showing first 10)" if len(models) > 10 else ""
                    return False, f"Model '{model}' not found in {provider}. Available{hint}: {available}"
            except requests.ConnectionError:
                return False, f"{provider} service not running. Start with: {start_hint}"
            except requests.Timeout:
                return False, f"{provider} service timeout. Check if service is running"
            except Exception as e:
                return False, f"Error checking {provider} availability: {str(e)}"
        elif provider in available_models:
            # Cloud providers: check against static model list
            if model not in available_models[provider]:
                return False, f"Model {model} not available for {provider}. Available models: {', '.join(available_models[provider])}"
        else:
            return False, f"Unknown provider: {provider}. Available: {', '.join(list(available_models.keys()) + list(local_providers.keys()))}"

        # Check API keys
        required_key = provider_requirements.get(provider)
        if required_key and not os.getenv(required_key):
            return False, f"Missing environment variable: {required_key}"

        return True, None
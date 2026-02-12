"""
Tests for per-model capabilities registry (MODEL_CAPABILITIES).

Tests cover:
- Phase 1: ModelCapability data model + registry + lookup (14 tests)
- Phase 2: Pre-flight tool support validation (5 tests)
- Phase 3: get_model_settings rewrite + GPT-5 bug fix (7 tests)
"""

import pytest
from pydantic import ValidationError
from agents import ModelSettings


# ── Phase 1: ModelCapability data model + registry + lookup ──


class TestModelCapabilityDataModel:
    """Tests for ModelCapability Pydantic model."""

    def test_model_capability_defaults(self):
        """ModelCapability() has sensible defaults."""
        from nano_agent.modules.data_types import ModelCapability

        cap = ModelCapability()
        assert cap.temperature == 0.2
        assert cap.max_tokens == 16000
        assert cap.supports_tools is True
        assert cap.supports_temperature is True
        assert cap.top_p is None

    def test_model_capability_custom_values(self):
        """Custom values are stored correctly."""
        from nano_agent.modules.data_types import ModelCapability

        cap = ModelCapability(temperature=1.0, max_tokens=131072, top_p=0.95)
        assert cap.temperature == 1.0
        assert cap.max_tokens == 131072
        assert cap.top_p == 0.95

    def test_model_capability_validation_rejects_negative_temp(self):
        """Negative temperature is rejected."""
        from nano_agent.modules.data_types import ModelCapability

        with pytest.raises(ValidationError):
            ModelCapability(temperature=-0.1)

    def test_model_capability_validation_rejects_zero_tokens(self):
        """Zero max_tokens is rejected (must be > 0)."""
        from nano_agent.modules.data_types import ModelCapability

        with pytest.raises(ValidationError):
            ModelCapability(max_tokens=0)


class TestRegistryContents:
    """Tests for MODEL_CAPABILITIES registry completeness."""

    def test_registry_has_all_known_models(self):
        """Every model in AVAILABLE_MODELS + ZAI_AVAILABLE_MODELS is in registry."""
        from nano_agent.modules.constants import (
            AVAILABLE_MODELS,
            ZAI_AVAILABLE_MODELS,
            QWEN_AVAILABLE_MODELS,
            MODEL_CAPABILITIES,
        )

        all_models = set()
        for models in AVAILABLE_MODELS.values():
            all_models.update(models)
        all_models.update(ZAI_AVAILABLE_MODELS)
        all_models.update(QWEN_AVAILABLE_MODELS)

        missing = all_models - set(MODEL_CAPABILITIES.keys())
        assert not missing, f"Models missing from MODEL_CAPABILITIES: {missing}"

    def test_glm47_has_full_output_capacity(self):
        """GLM-4.7 gets its full 131K output capacity."""
        from nano_agent.modules.constants import MODEL_CAPABILITIES

        assert MODEL_CAPABILITIES["glm-4.7"].max_tokens == 131072

    def test_gemma3_no_tool_support(self):
        """Gemma3:27b is marked as not supporting tools."""
        from nano_agent.modules.constants import MODEL_CAPABILITIES

        assert MODEL_CAPABILITIES["gemma3:27b"].supports_tools is False

    def test_gpt5_no_custom_temperature(self):
        """GPT-5 is marked as not supporting custom temperature."""
        from nano_agent.modules.constants import MODEL_CAPABILITIES

        assert MODEL_CAPABILITIES["gpt-5"].supports_temperature is False

    def test_all_models_have_positive_max_tokens(self):
        """Every model in registry has max_tokens > 0."""
        from nano_agent.modules.constants import MODEL_CAPABILITIES

        for model_name, cap in MODEL_CAPABILITIES.items():
            assert cap.max_tokens > 0, f"{model_name} has max_tokens={cap.max_tokens}"


class TestLookupFunction:
    """Tests for get_model_capabilities() lookup."""

    def test_get_model_capabilities_known_model(self):
        """Known model returns the correct registry entry."""
        from nano_agent.modules.constants import (
            get_model_capabilities,
            MODEL_CAPABILITIES,
        )

        cap = get_model_capabilities("glm-4.7")
        assert cap is MODEL_CAPABILITIES["glm-4.7"]

    def test_get_model_capabilities_unknown_model(self):
        """Unknown model returns DEFAULT_MODEL_CAPABILITY."""
        from nano_agent.modules.constants import (
            get_model_capabilities,
            DEFAULT_MODEL_CAPABILITY,
        )

        cap = get_model_capabilities("nonexistent-model")
        assert cap is DEFAULT_MODEL_CAPABILITY

    def test_get_model_capabilities_unknown_returns_defaults(self):
        """Unknown model fallback has correct default values."""
        from nano_agent.modules.constants import get_model_capabilities

        cap = get_model_capabilities("nonexistent-model")
        assert cap.temperature == 0.2
        assert cap.max_tokens == 16000

    def test_default_model_capability_matches_constructor(self):
        """DEFAULT_MODEL_CAPABILITY equals a fresh ModelCapability()."""
        from nano_agent.modules.constants import DEFAULT_MODEL_CAPABILITY
        from nano_agent.modules.data_types import ModelCapability

        assert DEFAULT_MODEL_CAPABILITY == ModelCapability()

    def test_get_model_capabilities_returns_correct_type(self):
        """Return type is ModelCapability."""
        from nano_agent.modules.constants import get_model_capabilities
        from nano_agent.modules.data_types import ModelCapability

        cap = get_model_capabilities("gpt-5-mini")
        assert isinstance(cap, ModelCapability)


# ── Phase 2: Pre-flight tool support validation ──


class TestToolSupportValidation:
    """Tests for ProviderConfig.validate_tool_support()."""

    def test_validate_tool_support_supported_model(self):
        """Supported model returns (True, None)."""
        from nano_agent.modules.provider_config import ProviderConfig

        ok, err = ProviderConfig.validate_tool_support("gpt-5-mini")
        assert ok is True
        assert err is None

    def test_validate_tool_support_unsupported_model(self):
        """Unsupported model returns (False, error_message)."""
        from nano_agent.modules.provider_config import ProviderConfig

        ok, err = ProviderConfig.validate_tool_support("gemma3:27b")
        assert ok is False
        assert "does not support tool calling" in err

    def test_validate_tool_support_unknown_model(self):
        """Unknown model defaults to supported (fallback assumes tools=True)."""
        from nano_agent.modules.provider_config import ProviderConfig

        ok, err = ProviderConfig.validate_tool_support("new-model-xyz")
        assert ok is True
        assert err is None

    def test_validate_tool_support_error_message_helpful(self):
        """Error message contains model name and a suggestion."""
        from nano_agent.modules.provider_config import ProviderConfig

        ok, err = ProviderConfig.validate_tool_support("gemma3:27b")
        assert "gemma3:27b" in err
        assert "qwen3-coder:30b" in err or "gpt-5-mini" in err

    def test_validate_tool_support_glm47_supported(self):
        """GLM-4.7 supports tools."""
        from nano_agent.modules.provider_config import ProviderConfig

        ok, err = ProviderConfig.validate_tool_support("glm-4.7")
        assert ok is True
        assert err is None


# ── Phase 3: get_model_settings rewrite + GPT-5 bug fix ──


class TestGetModelSettings:
    """Tests for rewritten get_model_settings()."""

    def test_get_model_settings_glm47(self):
        """GLM-4.7 gets full capacity settings."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("glm-4.7", "zai")
        assert ms.max_tokens == 131072
        assert ms.temperature == 1.0
        assert ms.top_p == 0.95

    def test_get_model_settings_gpt5_no_temperature(self):
        """GPT-5: temperature not set (None), max_tokens correct."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("gpt-5", "openai")
        assert ms.temperature is None  # Not set — SDK uses default (1.0)
        assert ms.max_tokens == 100000

    def test_get_model_settings_gpt5_mini(self):
        """GPT-5-mini gets temperature=0.2 and max_tokens=32000."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("gpt-5-mini", "openai")
        assert ms.temperature == 0.2
        assert ms.max_tokens == 32000

    def test_get_model_settings_unknown_model_uses_defaults(self):
        """Unknown model gets fallback defaults."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("unknown-model", "openai")
        assert ms.temperature == 0.2
        assert ms.max_tokens == 16000

    def test_get_model_settings_gemma3(self):
        """Gemma3 gets correct max_tokens (tool support is separate)."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("gemma3:27b", "ollama")
        assert ms.max_tokens == 8192

    def test_get_model_settings_returns_model_settings_type(self):
        """Return type is ModelSettings."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("gpt-5-mini", "openai")
        assert isinstance(ms, ModelSettings)

    def test_get_model_settings_no_base_settings_parameter(self):
        """New signature: (model, provider) only — no base_settings."""
        import inspect
        from nano_agent.modules.provider_config import ProviderConfig

        sig = inspect.signature(ProviderConfig.get_model_settings)
        params = list(sig.parameters.keys())
        assert "base_settings" not in params
        assert "model" in params
        assert "provider" in params


# ── Phase 4: Review hardening — regression guards + integration + edge cases ──


class TestRegressionGuards:
    """Regression guards for known bugs that were fixed."""

    def test_gpt5_uses_max_tokens_not_max_completion_tokens(self):
        """Regression: GPT-5 must use max_tokens field, not max_completion_tokens.

        The OpenAI raw API uses max_completion_tokens, but the Agent SDK's
        ModelSettings uses max_tokens. Using the wrong field silently drops the value.
        """
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("gpt-5", "openai")
        assert ms.max_tokens == 100000
        assert getattr(ms, "max_completion_tokens", None) is None

    def test_unknown_model_fallback_has_no_top_p(self):
        """Unknown model fallback should not set top_p."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("unknown-model", "openai")
        assert ms.top_p is None

    def test_model_name_lookup_is_case_sensitive(self):
        """Lookup is case-sensitive: 'GPT-5' != 'gpt-5'."""
        from nano_agent.modules.constants import get_model_capabilities, DEFAULT_MODEL_CAPABILITY

        cap = get_model_capabilities("GPT-5")
        assert cap is DEFAULT_MODEL_CAPABILITY


class TestIntegrationPipeline:
    """Integration tests: validate + settings compose correctly."""

    def test_glm47_full_pipeline(self):
        """GLM-4.7: passes validation, gets full-capacity ModelSettings."""
        from nano_agent.modules.provider_config import ProviderConfig
        from agents import ModelSettings

        ok, err = ProviderConfig.validate_tool_support("glm-4.7")
        assert ok is True

        ms = ProviderConfig.get_model_settings("glm-4.7", "zai")
        assert isinstance(ms, ModelSettings)
        assert ms.temperature == 1.0
        assert ms.max_tokens == 131072
        assert ms.top_p == 0.95

    def test_gpt5_full_pipeline(self):
        """GPT-5: passes validation, temperature omitted, max_tokens correct."""
        from nano_agent.modules.provider_config import ProviderConfig
        from agents import ModelSettings

        ok, err = ProviderConfig.validate_tool_support("gpt-5")
        assert ok is True

        ms = ProviderConfig.get_model_settings("gpt-5", "openai")
        assert isinstance(ms, ModelSettings)
        assert ms.temperature is None
        assert ms.max_tokens == 100000
        assert ms.top_p is None

    def test_gemma3_rejected_before_settings(self):
        """Gemma3: rejected at validation, never reaches settings."""
        from nano_agent.modules.provider_config import ProviderConfig

        ok, err = ProviderConfig.validate_tool_support("gemma3:27b")
        assert ok is False
        assert "does not support tool calling" in err

    def test_models_without_top_p_have_none(self):
        """Models without top_p in registry produce ModelSettings.top_p=None."""
        from nano_agent.modules.provider_config import ProviderConfig

        ms = ProviderConfig.get_model_settings("gpt-5-mini", "openai")
        assert ms.top_p is None


class TestBoundaryValues:
    """Boundary value tests for Pydantic validators."""

    def test_temperature_at_zero(self):
        """temperature=0.0 is valid (ge=0.0 boundary)."""
        from nano_agent.modules.data_types import ModelCapability

        assert ModelCapability(temperature=0.0).temperature == 0.0

    def test_temperature_at_max(self):
        """temperature=2.0 is valid (le=2.0 boundary)."""
        from nano_agent.modules.data_types import ModelCapability

        assert ModelCapability(temperature=2.0).temperature == 2.0

    def test_temperature_above_max_rejected(self):
        """temperature=2.01 is rejected."""
        from nano_agent.modules.data_types import ModelCapability

        with pytest.raises(ValidationError):
            ModelCapability(temperature=2.01)

    def test_max_tokens_one_is_valid(self):
        """max_tokens=1 is valid (gt=0 means minimum is 1)."""
        from nano_agent.modules.data_types import ModelCapability

        assert ModelCapability(max_tokens=1).max_tokens == 1

    def test_negative_max_tokens_rejected(self):
        """Negative max_tokens is rejected."""
        from nano_agent.modules.data_types import ModelCapability

        with pytest.raises(ValidationError):
            ModelCapability(max_tokens=-1)


# ── Phase 5: Qwen Cloud provider registration ──


class TestQwenRegistration:
    """Tests for Qwen Cloud provider constants and type registration."""

    def test_registry_has_coder_model(self):
        """coder-model is in MODEL_CAPABILITIES."""
        from nano_agent.modules.constants import MODEL_CAPABILITIES

        assert "coder-model" in MODEL_CAPABILITIES

    def test_coder_model_capabilities(self):
        """coder-model has correct capability values."""
        from nano_agent.modules.constants import MODEL_CAPABILITIES

        cap = MODEL_CAPABILITIES["coder-model"]
        assert cap.temperature == 0.7
        assert cap.max_tokens == 65536
        assert cap.top_p == 0.8
        assert cap.supports_tools is True

    def test_qwen_provider_requirements_is_none(self):
        """Qwen uses file-based OAuth, not env var."""
        from nano_agent.modules.constants import PROVIDER_REQUIREMENTS

        assert PROVIDER_REQUIREMENTS["qwen"] is None

    def test_qwen_available_models(self):
        """QWEN_AVAILABLE_MODELS contains coder-model."""
        from nano_agent.modules.constants import QWEN_AVAILABLE_MODELS

        assert QWEN_AVAILABLE_MODELS == ["coder-model"]

    def test_prompt_request_accepts_qwen_provider(self):
        """PromptNanoAgentRequest accepts provider='qwen'."""
        from nano_agent.modules.data_types import PromptNanoAgentRequest

        req = PromptNanoAgentRequest(agentic_prompt="test", provider="qwen")
        assert req.provider == "qwen"

    def test_launch_request_accepts_qwen_provider(self):
        """LaunchAgentRequest accepts provider='qwen'."""
        from nano_agent.modules.data_types import LaunchAgentRequest

        req = LaunchAgentRequest(agentic_prompt="test", agent_path="/tmp", provider="qwen")
        assert req.provider == "qwen"

    def test_get_model_settings_coder_model(self):
        """coder-model gets correct ModelSettings from registry."""
        from nano_agent.modules.provider_config import ProviderConfig
        from agents import ModelSettings

        ms = ProviderConfig.get_model_settings("coder-model", "qwen")
        assert isinstance(ms, ModelSettings)
        assert ms.temperature == 0.7
        assert ms.max_tokens == 65536
        assert ms.top_p == 0.8

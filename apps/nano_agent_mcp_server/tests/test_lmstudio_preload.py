"""Tests for LM Studio pre-load functionality (R3)."""
import pytest
from nano_agent.modules.constants import LMSTUDIO_BASE_URL


# ============================================================================
# Phase 1: LMSTUDIO_BASE_URL constant tests
# ============================================================================

def test_lmstudio_base_url_constant_exists():
    """LMSTUDIO_BASE_URL is defined in constants."""
    assert LMSTUDIO_BASE_URL == "http://127.0.0.1:1234"


def test_local_provider_config_uses_constant():
    """LOCAL_PROVIDER_CONFIG lmstudio entry uses LMSTUDIO_BASE_URL."""
    from nano_agent.modules.provider_config import LOCAL_PROVIDER_CONFIG
    assert LOCAL_PROVIDER_CONFIG["lmstudio"][0] == LMSTUDIO_BASE_URL


def test_web_server_uses_lmstudio_constant():
    """web/server.py LOCAL_PROVIDERS uses LMSTUDIO_BASE_URL."""
    from nano_agent.web.server import LOCAL_PROVIDERS
    assert LOCAL_PROVIDERS["lmstudio"]["url"] == LMSTUDIO_BASE_URL


# ============================================================================
# Phase 2: Matching helper tests
# ============================================================================

from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from nano_agent.modules.provider_config import _matches_lmstudio_model, _resolve_lmstudio_model_key


class TestMatchesLmstudioModel:
    """Tests for _matches_lmstudio_model helper."""

    def test_exact_match(self):
        assert _matches_lmstudio_model("qwen/qwen3-coder-next", "qwen/qwen3-coder-next") is True

    def test_case_insensitive(self):
        assert _matches_lmstudio_model("Qwen/Qwen3-Coder-Next", "qwen/qwen3-coder-next") is True

    def test_suffix_match(self):
        """key has publisher prefix, model is short form."""
        assert _matches_lmstudio_model("qwen/qwen3-coder-next", "qwen3-coder-next") is True

    def test_instance_suffix_strip(self):
        """key has :N instance suffix."""
        assert _matches_lmstudio_model("qwen/qwen3-coder-next:2", "qwen/qwen3-coder-next") is True

    def test_no_match(self):
        assert _matches_lmstudio_model("openai/gpt-oss-20b", "qwen/qwen3-coder-next") is False

    def test_instance_suffix_with_short_model(self):
        """key has :N suffix, model is short form."""
        assert _matches_lmstudio_model("qwen/qwen3-coder-next:3", "qwen3-coder-next") is True

    def test_non_numeric_colon_not_stripped(self):
        """Colon in model name (not instance suffix) should not be stripped."""
        assert _matches_lmstudio_model("qwen3-coder:30b", "qwen3-coder:30b") is True


class TestResolveLmstudioModelKey:
    """Tests for _resolve_lmstudio_model_key helper."""

    def test_exact_match(self):
        models = [{"key": "qwen/qwen3-coder-next"}, {"key": "openai/gpt-oss-20b"}]
        key, err = _resolve_lmstudio_model_key("qwen/qwen3-coder-next", models)
        assert key == "qwen/qwen3-coder-next"
        assert err is None

    def test_case_insensitive_exact(self):
        models = [{"key": "Qwen/Qwen3-Coder-Next"}]
        key, err = _resolve_lmstudio_model_key("qwen/qwen3-coder-next", models)
        assert key == "Qwen/Qwen3-Coder-Next"
        assert err is None

    def test_suffix_resolve(self):
        models = [{"key": "qwen/qwen3-coder-next"}, {"key": "openai/gpt-oss-20b"}]
        key, err = _resolve_lmstudio_model_key("qwen3-coder-next", models)
        assert key == "qwen/qwen3-coder-next"
        assert err is None

    def test_ambiguous_returns_error(self):
        models = [{"key": "pub-a/model-x"}, {"key": "pub-b/model-x"}]
        key, err = _resolve_lmstudio_model_key("model-x", models)
        assert key is None
        assert "Ambiguous" in err
        assert "pub-a/model-x" in err
        assert "pub-b/model-x" in err

    def test_not_found(self):
        models = [{"key": "openai/gpt-oss-20b"}]
        key, err = _resolve_lmstudio_model_key("nonexistent-model", models)
        assert key is None
        assert err is None


# ============================================================================
# Phase 2: Async preload tests
# ============================================================================

from nano_agent.modules.provider_config import ProviderConfig


def _make_models_response(models_list):
    """Helper: create a mock GET /api/v1/models response."""
    return {"models": models_list}


def _make_model_entry(key, loaded=False):
    """Helper: create a single model entry for GET /api/v1/models."""
    entry = {"key": key, "loaded_instances": []}
    if loaded:
        entry["loaded_instances"] = [{"id": key, "config": {"context_length": 4096}}]
    return entry


class TestPreloadLmstudioModelAsync:
    """Tests for ProviderConfig.preload_lmstudio_model_async."""

    @pytest.mark.asyncio
    async def test_already_loaded_skips_post(self):
        """If model is already loaded, return success without calling POST."""
        mock_client = AsyncMock()
        # GET /api/v1/models returns model with loaded_instances
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=True)
        ])
        mock_client.get.return_value = check_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is True
        assert err is None
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_success(self):
        """Model not loaded -> POST succeeds -> verification confirms loaded."""
        mock_client = AsyncMock()
        # First GET: model exists but not loaded
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        # POST: success
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.json.return_value = {"type": "llm", "status": "loaded"}
        # Second GET (verification): now loaded
        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=True)
        ])
        mock_client.get.side_effect = [check_response, verify_response]
        mock_client.post.return_value = post_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is True
        assert err is None
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_failure(self):
        """POST returns non-200 -> return error."""
        mock_client = AsyncMock()
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_response = MagicMock()
        post_response.status_code = 500
        post_response.text = "Internal Server Error"
        mock_client.get.return_value = check_response
        mock_client.post.return_value = post_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Failed to pre-load" in err

    @pytest.mark.asyncio
    async def test_memory_error(self):
        """POST fails with memory error keywords -> specific error."""
        mock_client = AsyncMock()
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_response = MagicMock()
        post_response.status_code = 500
        post_response.text = "Insufficient VRAM to load model"
        mock_client.get.return_value = check_response
        mock_client.post.return_value = post_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Insufficient memory" in err

    @pytest.mark.asyncio
    async def test_model_not_found(self):
        """Model not in native model list -> error."""
        mock_client = AsyncMock()
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("openai/gpt-oss-20b", loaded=False)
        ])
        mock_client.get.return_value = check_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "nonexistent-model", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "not found" in err

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """LM Studio not running -> connection error."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "not running" in err

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Load times out -> timeout error."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Timeout" in err

    @pytest.mark.asyncio
    async def test_verification_fails(self):
        """POST ok but verification GET shows not loaded."""
        mock_client = AsyncMock()
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_response = MagicMock()
        post_response.status_code = 200
        # Verification: still not loaded
        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        mock_client.get.side_effect = [check_response, verify_response]
        mock_client.post.return_value = post_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "verification failed" in err

    @pytest.mark.asyncio
    async def test_ambiguous_model(self):
        """Ambiguous model name -> error."""
        mock_client = AsyncMock()
        check_response = MagicMock()
        check_response.status_code = 200
        check_response.json.return_value = _make_models_response([
            _make_model_entry("pub-a/model-x"),
            _make_model_entry("pub-b/model-x"),
        ])
        mock_client.get.return_value = check_response

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            ok, err = await ProviderConfig.preload_lmstudio_model_async(
                "model-x", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Ambiguous" in err


# ============================================================================
# Phase 2: Sync preload tests
# ============================================================================

class TestPreloadLmstudioModelSync:
    """Tests for ProviderConfig.preload_lmstudio_model (sync)."""

    def test_already_loaded_skips_post(self):
        """If model is already loaded, return success without calling POST."""
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=True)
        ])

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.return_value = mock_get
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is True
        assert err is None
        mock_req.post.assert_not_called()

    def test_load_success(self):
        """Model not loaded -> POST succeeds -> verification confirms."""
        check_resp = MagicMock()
        check_resp.status_code = 200
        check_resp.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_resp = MagicMock()
        post_resp.status_code = 200
        verify_resp = MagicMock()
        verify_resp.status_code = 200
        verify_resp.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=True)
        ])

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.side_effect = [check_resp, verify_resp]
            mock_req.post.return_value = post_resp
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is True
        assert err is None

    def test_load_failure(self):
        """POST returns non-200 -> return error."""
        check_resp = MagicMock()
        check_resp.status_code = 200
        check_resp.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_resp = MagicMock()
        post_resp.status_code = 500
        post_resp.text = "Internal Server Error"

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.return_value = check_resp
            mock_req.post.return_value = post_resp
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Failed to pre-load" in err

    def test_memory_error(self):
        """POST fails with memory keywords -> specific error."""
        check_resp = MagicMock()
        check_resp.status_code = 200
        check_resp.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_resp = MagicMock()
        post_resp.status_code = 500
        post_resp.text = "Insufficient VRAM to load model"

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.return_value = check_resp
            mock_req.post.return_value = post_resp
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Insufficient memory" in err

    def test_model_not_found(self):
        """Model not in native model list -> error."""
        check_resp = MagicMock()
        check_resp.status_code = 200
        check_resp.json.return_value = _make_models_response([
            _make_model_entry("openai/gpt-oss-20b", loaded=False)
        ])

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.return_value = check_resp
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "nonexistent-model", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "not found" in err

    def test_connection_error(self):
        """LM Studio not running -> connection error."""
        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.side_effect = ConnectionError("Connection refused")
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "not running" in err

    def test_timeout(self):
        """Load times out -> timeout error."""
        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.side_effect = TimeoutError("Request timed out")
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Timeout" in err

    def test_verification_fails(self):
        """POST ok but verification shows not loaded."""
        check_resp = MagicMock()
        check_resp.status_code = 200
        check_resp.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])
        post_resp = MagicMock()
        post_resp.status_code = 200
        verify_resp = MagicMock()
        verify_resp.status_code = 200
        verify_resp.json.return_value = _make_models_response([
            _make_model_entry("qwen/qwen3-coder-next", loaded=False)
        ])

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.side_effect = [check_resp, verify_resp]
            mock_req.post.return_value = post_resp
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "qwen/qwen3-coder-next", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "verification failed" in err

    def test_ambiguous_model(self):
        """Ambiguous model name -> error."""
        check_resp = MagicMock()
        check_resp.status_code = 200
        check_resp.json.return_value = _make_models_response([
            _make_model_entry("pub-a/model-x"),
            _make_model_entry("pub-b/model-x"),
        ])

        with patch("nano_agent.modules.provider_config.requests") as mock_req:
            mock_req.get.return_value = check_resp
            mock_req.ConnectionError = ConnectionError
            mock_req.Timeout = TimeoutError
            ok, err = ProviderConfig.preload_lmstudio_model(
                "model-x", "http://127.0.0.1:1234"
            )

        assert ok is False
        assert "Ambiguous" in err


# ============================================================================
# Phase 3: Execution path wiring tests
# ============================================================================

from nano_agent.modules.constants import LMSTUDIO_BASE_URL as LMSTUDIO_BASE_URL_CONST


@pytest.mark.asyncio
async def test_execute_async_lmstudio_preload_called():
    """Preload is called for lmstudio provider in async path."""
    with patch("nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
               new_callable=AsyncMock, return_value=(True, None)) as mock_preload, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
               new_callable=AsyncMock, return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.setup_provider"), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.create_agent") as mock_create, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.get_model_settings", return_value=None), \
         patch("nano_agent.modules.nano_agent.Runner") as mock_runner, \
         patch("nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"), \
         patch("nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        mock_result = MagicMock()
        mock_result.final_output = "done"
        mock_runner.run = AsyncMock(return_value=mock_result)

        from nano_agent.modules.nano_agent import NanoAgent
        from nano_agent.modules.data_types import PromptNanoAgentRequest
        agent = NanoAgent()
        request = PromptNanoAgentRequest(
            agentic_prompt="test",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
            workspace="/tmp"
        )
        result = await agent.execute_nano_agent_async(request)
        mock_preload.assert_called_once_with("qwen/qwen3-coder-next", LMSTUDIO_BASE_URL_CONST)

@pytest.mark.asyncio
async def test_execute_async_non_lmstudio_preload_skipped():
    """Preload is NOT called for non-lmstudio providers."""
    with patch("nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
               new_callable=AsyncMock) as mock_preload, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
               new_callable=AsyncMock, return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.setup_provider"), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.create_agent") as mock_create, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.get_model_settings", return_value=None), \
         patch("nano_agent.modules.nano_agent.Runner") as mock_runner, \
         patch("nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"), \
         patch("nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        mock_result = MagicMock()
        mock_result.final_output = "done"
        mock_runner.run = AsyncMock(return_value=mock_result)

        from nano_agent.modules.nano_agent import NanoAgent
        from nano_agent.modules.data_types import PromptNanoAgentRequest
        agent = NanoAgent()
        request = PromptNanoAgentRequest(
            agentic_prompt="test",
            model="gpt-5-mini",
            provider="openai",
            workspace="/tmp"
        )
        result = await agent.execute_nano_agent_async(request)
        mock_preload.assert_not_called()

@pytest.mark.asyncio
async def test_execute_async_preload_failure_returns_error():
    """If preload fails, execution returns error without reaching Runner."""
    with patch("nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
               new_callable=AsyncMock, return_value=(False, "Model not found")) as mock_preload, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
               new_callable=AsyncMock, return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.Runner") as mock_runner:

        from nano_agent.modules.nano_agent import NanoAgent
        from nano_agent.modules.data_types import PromptNanoAgentRequest
        agent = NanoAgent()
        request = PromptNanoAgentRequest(
            agentic_prompt="test",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
            workspace="/tmp"
        )
        result = await agent.execute_nano_agent_async(request)
        assert result.success is False
        assert "Model not found" in result.error
        mock_runner.run.assert_not_called()

def test_execute_sync_lmstudio_preload_called():
    """Preload is called for lmstudio provider in sync path."""
    with patch("nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model",
               return_value=(True, None)) as mock_preload, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.setup_provider"), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.create_agent") as mock_create, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.get_model_settings", return_value=None), \
         patch("nano_agent.modules.nano_agent.Runner") as mock_runner, \
         patch("nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"), \
         patch("nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        mock_result = MagicMock()
        mock_result.final_output = "done"
        mock_runner.run_sync.return_value = mock_result

        from nano_agent.modules.nano_agent import NanoAgent
        from nano_agent.modules.data_types import PromptNanoAgentRequest
        agent = NanoAgent()
        request = PromptNanoAgentRequest(
            agentic_prompt="test",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
            workspace="/tmp"
        )
        result = agent._execute_nano_agent(request)
        mock_preload.assert_called_once_with("qwen/qwen3-coder-next", LMSTUDIO_BASE_URL_CONST)

def test_execute_sync_preload_failure_returns_error():
    """If preload fails in sync path, execution returns error."""
    with patch("nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model",
               return_value=(False, "Service not running")) as mock_preload, \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup", return_value=(True, None)), \
         patch("nano_agent.modules.nano_agent.Runner") as mock_runner:

        from nano_agent.modules.nano_agent import NanoAgent
        from nano_agent.modules.data_types import PromptNanoAgentRequest
        agent = NanoAgent()
        request = PromptNanoAgentRequest(
            agentic_prompt="test",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
            workspace="/tmp"
        )
        result = agent._execute_nano_agent(request)
        assert result.success is False
        assert "Service not running" in result.error
        mock_runner.run_sync.assert_not_called()


# ============================================================================
# Phase 3: Wire preload into execution paths
# ============================================================================

from nano_agent.modules.nano_agent import _execute_nano_agent_async, _execute_nano_agent
from nano_agent.modules.data_types import PromptNanoAgentRequest


class TestExecuteAsyncLmstudioPreload:
    """Tests for preload integration in _execute_nano_agent_async."""

    @pytest.mark.asyncio
    async def test_lmstudio_preload_called(self):
        """Preload is called for lmstudio provider."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
            new_callable=AsyncMock, return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
            new_callable=AsyncMock, return_value=(True, None)
        ) as mock_preload, patch(
            "nano_agent.modules.nano_agent.ProviderConfig.setup_provider"
        ), patch(
            "nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"
        ), patch(
            "nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.get_model_settings",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.create_agent",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run",
            new_callable=AsyncMock,
            return_value=MagicMock(final_output="done")
        ):
            result = await _execute_nano_agent_async(request, enable_rich_logging=False)

        mock_preload.assert_called_once_with("qwen/qwen3-coder-next", LMSTUDIO_BASE_URL)

    @pytest.mark.asyncio
    async def test_non_lmstudio_preload_skipped(self):
        """Preload is NOT called for non-lmstudio providers."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="gpt-5-mini",
            provider="openai",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
            new_callable=AsyncMock, return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
            new_callable=AsyncMock
        ) as mock_preload, patch(
            "nano_agent.modules.nano_agent.ProviderConfig.setup_provider"
        ), patch(
            "nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"
        ), patch(
            "nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.get_model_settings",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.create_agent",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run",
            new_callable=AsyncMock,
            return_value=MagicMock(final_output="done")
        ):
            await _execute_nano_agent_async(request, enable_rich_logging=False)

        mock_preload.assert_not_called()

    @pytest.mark.asyncio
    async def test_preload_failure_returns_error(self):
        """If preload fails, execution returns error without reaching Runner."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
            new_callable=AsyncMock, return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
            new_callable=AsyncMock,
            return_value=(False, "LM Studio: Insufficient memory to load model")
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run",
            new_callable=AsyncMock
        ) as mock_runner:
            result = await _execute_nano_agent_async(request, enable_rich_logging=False)

        assert result.success is False
        assert "Insufficient memory" in result.error
        mock_runner.assert_not_called()

    @pytest.mark.asyncio
    async def test_preload_success_reaches_runner(self):
        """If preload succeeds, execution continues to Runner.run."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup_async",
            new_callable=AsyncMock, return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model_async",
            new_callable=AsyncMock, return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.setup_provider"
        ), patch(
            "nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"
        ), patch(
            "nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.get_model_settings",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.create_agent",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run",
            new_callable=AsyncMock,
            return_value=MagicMock(final_output="done")
        ) as mock_runner:
            result = await _execute_nano_agent_async(request, enable_rich_logging=False)

        assert result.success is True
        mock_runner.assert_called_once()


class TestExecuteSyncLmstudioPreload:
    """Tests for preload integration in _execute_nano_agent (sync)."""

    def test_lmstudio_preload_called(self):
        """Preload is called for lmstudio provider."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model",
            return_value=(True, None)
        ) as mock_preload, patch(
            "nano_agent.modules.nano_agent.ProviderConfig.setup_provider"
        ), patch(
            "nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"
        ), patch(
            "nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.get_model_settings",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.create_agent",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run_sync",
            return_value=MagicMock(final_output="done")
        ):
            result = _execute_nano_agent(request, enable_rich_logging=False)

        mock_preload.assert_called_once_with("qwen/qwen3-coder-next", LMSTUDIO_BASE_URL)

    def test_non_lmstudio_preload_skipped(self):
        """Preload is NOT called for non-lmstudio providers."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="gpt-5-mini",
            provider="openai",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model",
        ) as mock_preload, patch(
            "nano_agent.modules.nano_agent.ProviderConfig.setup_provider"
        ), patch(
            "nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"
        ), patch(
            "nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.get_model_settings",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.create_agent",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run_sync",
            return_value=MagicMock(final_output="done")
        ):
            _execute_nano_agent(request, enable_rich_logging=False)

        mock_preload.assert_not_called()

    def test_preload_failure_returns_error(self):
        """If preload fails, execution returns error without reaching Runner."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model",
            return_value=(False, "LM Studio: Insufficient memory to load model")
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run_sync"
        ) as mock_runner:
            result = _execute_nano_agent(request, enable_rich_logging=False)

        assert result.success is False
        assert "Insufficient memory" in result.error
        mock_runner.assert_not_called()

    def test_preload_success_reaches_runner(self):
        """If preload succeeds, execution continues to Runner.run_sync."""
        request = PromptNanoAgentRequest(
            agentic_prompt="test task",
            model="qwen/qwen3-coder-next",
            provider="lmstudio",
        )
        with patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_provider_setup",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.validate_tool_support",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.preload_lmstudio_model",
            return_value=(True, None)
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.setup_provider"
        ), patch(
            "nano_agent.modules.nano_agent.set_workspace", return_value="/tmp"
        ), patch(
            "nano_agent.modules.nano_agent.get_nano_agent_tools", return_value=[]
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.get_model_settings",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.ProviderConfig.create_agent",
            return_value=MagicMock()
        ), patch(
            "nano_agent.modules.nano_agent.Runner.run_sync",
            return_value=MagicMock(final_output="done")
        ) as mock_runner:
            result = _execute_nano_agent(request, enable_rich_logging=False)

        assert result.success is True
        mock_runner.assert_called_once()

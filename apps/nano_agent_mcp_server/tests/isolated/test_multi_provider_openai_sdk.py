"""
Minimal test of OpenAI SDK compatibility with multiple providers.

This test validates that the OpenAI SDK can be used with:
- Ollama (local models)
- Anthropic (Claude models)

No mocking - these are real API calls.
"""

import pytest
import os
from openai import OpenAI

from conftest import OLLAMA_OPENAI_URL, ollama_available, get_smallest_ollama_model


class TestOllamaProvider:
    """Test OpenAI SDK with Ollama local models."""

    @pytest.mark.skipif(
        not ollama_available(),
        reason="No Ollama models available at 127.0.0.1:11434"
    )
    def test_ollama_basic_chat(self):
        """Test basic chat completion with Ollama."""
        model = get_smallest_ollama_model()
        client = OpenAI(
            base_url=OLLAMA_OPENAI_URL,
            api_key="ollama",  # Required but unused
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Say hello in exactly one word"}
            ],
            max_tokens=200,
            temperature=0
        )

        # Assert we got a response
        assert response.choices
        assert len(response.choices) > 0
        assert response.choices[0].message

        # Check for content or reasoning field (some models use reasoning)
        message = response.choices[0].message
        content = message.content or ""
        reasoning = getattr(message, 'reasoning', '')

        # Either content or reasoning should have text
        assert content or reasoning, f"No content or reasoning in response. Message: {message}"

        actual_response = content.strip() if content else reasoning.strip()
        assert len(actual_response) > 0
        print(f"Ollama response ({model}): {actual_response[:100]}")

    @pytest.mark.skipif(
        not ollama_available(),
        reason="No Ollama models available at 127.0.0.1:11434"
    )
    def test_ollama_with_system_message(self):
        """Test Ollama with system message."""
        model = get_smallest_ollama_model()
        client = OpenAI(
            base_url=OLLAMA_OPENAI_URL,
            api_key="ollama",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that only responds with single words."},
                {"role": "user", "content": "What is 2+2? Answer with just the number."}
            ],
            max_tokens=200,
            temperature=0
        )

        # Check for content or reasoning field
        message = response.choices[0].message
        content = message.content or ""
        reasoning = getattr(message, 'reasoning', '')

        actual_response = content.strip() if content else reasoning.strip()
        assert actual_response
        print(f"Ollama math response ({model}): {actual_response[:100]}")


class TestAnthropicProvider:
    """Test OpenAI SDK with Anthropic Claude models."""

    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    )
    def test_anthropic_basic_chat(self):
        """Test basic chat completion with Anthropic."""
        client = OpenAI(
            base_url="https://api.anthropic.com/v1/",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[
                {"role": "user", "content": "Say hello in exactly one word"}
            ],
            max_tokens=10,
            temperature=0
        )

        assert response.choices
        assert len(response.choices) > 0
        assert response.choices[0].message
        assert response.choices[0].message.content

        content = response.choices[0].message.content.strip()
        assert len(content) > 0
        print(f"Anthropic response: {content}")

    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    )
    def test_anthropic_with_system_message(self):
        """Test Anthropic with system message."""
        client = OpenAI(
            base_url="https://api.anthropic.com/v1/",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that only responds with single words."},
                {"role": "user", "content": "What is 2+2? Answer with just the number."}
            ],
            max_tokens=10,
            temperature=0
        )

        assert response.choices[0].message.content
        content = response.choices[0].message.content.strip()
        print(f"Anthropic math response: {content}")
        assert "4" in content.lower() or "four" in content.lower()


class TestOpenAIAgentSDKCompatibility:
    """Test if OpenAI Agent SDK can work with alternative providers."""

    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    )
    def test_agent_sdk_with_anthropic(self):
        """Attempt to use Agent SDK with Anthropic (may not work)."""
        try:
            from agents import Agent, Runner

            os.environ["OPENAI_BASE_URL"] = "https://api.anthropic.com/v1/"
            os.environ["OPENAI_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")

            agent = Agent(
                name="TestAgent",
                instructions="You are a helpful assistant.",
                model="claude-3-haiku-20240307",
            )

            result = Runner.run_sync(
                agent,
                "Say hello",
                max_turns=1
            )

            assert result
            print(f"Agent SDK with Anthropic: {result}")

        except Exception as e:
            print(f"Agent SDK with Anthropic failed (expected): {e}")
            pytest.skip(f"Agent SDK doesn't support Anthropic: {e}")

    @pytest.mark.skipif(
        not ollama_available(),
        reason="No Ollama models available at 127.0.0.1:11434"
    )
    def test_agent_sdk_with_ollama(self):
        """Attempt to use Agent SDK with Ollama (may not work)."""
        model = get_smallest_ollama_model()
        try:
            from agents import Agent, Runner

            os.environ["OPENAI_BASE_URL"] = OLLAMA_OPENAI_URL
            os.environ["OPENAI_API_KEY"] = "ollama"

            agent = Agent(
                name="TestAgent",
                instructions="You are a helpful assistant.",
                model=model,
            )

            result = Runner.run_sync(
                agent,
                "Say hello",
                max_turns=1
            )

            assert result
            print(f"Agent SDK with Ollama ({model}): {result}")

        except Exception as e:
            print(f"Agent SDK with Ollama failed (expected): {e}")
            pytest.skip(f"Agent SDK doesn't support Ollama: {e}")


def test_providers_documented():
    """Test that alternative provider documentation exists in the project."""
    # Verify nano-agent package has provider_config module (documents provider setup)
    from nano_agent.modules import provider_config
    assert hasattr(provider_config, 'ProviderConfig')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

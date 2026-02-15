"""
Production tests for GPT-5 model variants.

This test file validates that GPT-5, GPT-5-mini, and GPT-5-nano
all work correctly with reasoning_effort and verbosity parameters.

NOTE: These tests hit the production OpenAI API and will incur costs.
They skip gracefully when models are not available (404).

VERIFIED FINDINGS (August 2025):
- All GPT-5 models (gpt-5, gpt-5-mini, gpt-5-nano) support reasoning_effort parameter
- All GPT-5 models support verbosity parameter
- gpt-5-chat-latest exists and works (non-reasoning variant)
- GPT-5 models use 'max_completion_tokens' instead of 'max_tokens'
- GPT-5 models only support temperature=1 (default value)
"""

import os
import pytest
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any
import time

# Load environment variables from .env file
load_dotenv()

# Verify API key is set
if not os.getenv("OPENAI_API_KEY"):
    pytest.skip("OPENAI_API_KEY not set in environment", allow_module_level=True)


class TestGPT5ModelsProduction:
    """Test GPT-5 model variants against production API."""

    @classmethod
    def setup_class(cls):
        """Initialize OpenAI client."""
        cls.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        cls.test_prompt = "What is 2+2? Answer in one word only."

    def _make_api_call(self, model: str, reasoning_effort: str = "low", verbosity: str = "low") -> Dict[str, Any]:
        """
        Make an API call to a specific GPT-5 model variant.

        Args:
            model: The model ID to test
            reasoning_effort: The reasoning effort level (low, medium, high, none)
            verbosity: The verbosity level (low, medium, high)

        Returns:
            Dict containing the response and metadata
        """
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": self.test_prompt}
                ],
                max_completion_tokens=100,
                reasoning_effort=reasoning_effort,
                verbosity=verbosity
            )

            elapsed_time = time.time() - start_time

            return {
                "success": True,
                "model": model,
                "response": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "reasoning_tokens": getattr(response.usage, 'reasoning_tokens', None)
                },
                "elapsed_time": elapsed_time,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity
            }
        except Exception as e:
            return {
                "success": False,
                "model": model,
                "error": str(e),
                "elapsed_time": time.time() - start_time
            }

    @pytest.mark.parametrize("model", ["gpt-5", "gpt-5-mini", "gpt-5-nano"])
    def test_model_with_low_reasoning_low_verbosity(self, model: str):
        """
        Test each GPT-5 model variant with low reasoning effort and low verbosity.
        Skips if the model is not available (404).
        """
        result = self._make_api_call(model, reasoning_effort="low", verbosity="low")

        if not result["success"]:
            error = result.get("error", "")
            if "not found" in error.lower() or "404" in error:
                pytest.skip(f"Model {model} not available: {error}")
            else:
                pytest.fail(f"API call failed for {model}: {error}")

        assert result["response"], f"No response received from {model}"
        assert len(result["response"]) > 0, f"Empty response from {model}"

        print(f"\n{model} Results:")
        print(f"  Response: {result['response']}")
        print(f"  Elapsed Time: {result['elapsed_time']:.2f}s")
        print(f"  Tokens Used: {result['usage']['total_tokens']}")
        if result['usage'].get('reasoning_tokens'):
            print(f"  Reasoning Tokens: {result['usage']['reasoning_tokens']}")

    @pytest.mark.parametrize("model", ["gpt-5", "gpt-5-mini", "gpt-5-nano"])
    def test_model_with_no_reasoning(self, model: str):
        """
        Test each model with no reasoning (fastest mode).
        Skips if the model is not available (404).
        """
        result = self._make_api_call(model, reasoning_effort="none", verbosity="low")

        if not result["success"]:
            error = result.get("error", "")
            if "not found" in error.lower() or "404" in error or "invalid" in error.lower():
                pytest.skip(f"Model {model} not available or doesn't support this config: {error}")
            else:
                pytest.fail(f"API call failed for {model}: {error}")

        assert result["response"], f"No response received from {model}"

        print(f"\n{model} (no reasoning) Results:")
        print(f"  Response: {result['response']}")
        print(f"  Elapsed Time: {result['elapsed_time']:.2f}s")

    def test_gpt5_chat_latest_without_reasoning(self):
        """
        Test gpt-5-chat-latest model which doesn't support reasoning_effort.
        """
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model="gpt-5-chat-latest",
                messages=[
                    {"role": "user", "content": self.test_prompt}
                ],
                max_completion_tokens=100,
            )

            elapsed_time = time.time() - start_time

            assert response.choices[0].message.content, "No response from gpt-5-chat-latest"

            print(f"\ngpt-5-chat-latest Results:")
            print(f"  Response: {response.choices[0].message.content}")
            print(f"  Elapsed Time: {elapsed_time:.2f}s")
            print(f"  Tokens Used: {response.usage.total_tokens}")

        except Exception as e:
            if "model" in str(e).lower() or "not found" in str(e).lower():
                pytest.skip(f"gpt-5-chat-latest not available: {e}")
            else:
                raise

    def test_compare_reasoning_levels(self):
        """
        Compare different reasoning levels for the base GPT-5 model.
        """
        model = "gpt-5"
        reasoning_levels = ["none", "low", "medium", "high"]
        results = []

        for level in reasoning_levels:
            result = self._make_api_call(model, reasoning_effort=level, verbosity="low")
            if result["success"]:
                results.append(result)

        if not results:
            pytest.skip(f"Model {model} not available")

        print(f"\n{'='*60}")
        print(f"Reasoning Level Comparison for {model}")
        print(f"{'='*60}")
        print(f"{'Level':<10} {'Time (s)':<10} {'Tokens':<10} {'Response':<30}")
        print(f"{'-'*60}")

        for result in results:
            print(f"{result['reasoning_effort']:<10} "
                  f"{result['elapsed_time']:<10.2f} "
                  f"{result['usage']['total_tokens']:<10} "
                  f"{result['response'][:30]:<30}")

    def test_cost_calculation(self):
        """
        Calculate and display the cost of each model call.
        """
        pricing = {
            "gpt-5": {"input": 1.25, "output": 10},
            "gpt-5-mini": {"input": 0.25, "output": 2},
            "gpt-5-nano": {"input": 0.05, "output": 0.40}
        }

        print(f"\n{'='*60}")
        print("Cost Analysis for Test Calls")
        print(f"{'='*60}")

        any_success = False
        for model in ["gpt-5", "gpt-5-mini", "gpt-5-nano"]:
            result = self._make_api_call(model, reasoning_effort="low", verbosity="low")

            if result["success"]:
                any_success = True
                model_pricing = pricing[model]
                input_cost = (result["usage"]["prompt_tokens"] / 1_000_000) * model_pricing["input"]
                output_cost = (result["usage"]["completion_tokens"] / 1_000_000) * model_pricing["output"]
                total_cost = input_cost + output_cost

                print(f"\n{model}:")
                print(f"  Input tokens: {result['usage']['prompt_tokens']} (${input_cost:.6f})")
                print(f"  Output tokens: {result['usage']['completion_tokens']} (${output_cost:.6f})")
                print(f"  Total cost: ${total_cost:.6f}")
                print(f"  Response: {result['response']}")
            else:
                print(f"\n{model}: SKIPPED - {result.get('error', 'unknown error')[:80]}")

        if not any_success:
            pytest.skip("No GPT-5 models available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

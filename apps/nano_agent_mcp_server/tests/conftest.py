"""Shared test fixtures and helpers for nano-agent tests.

Provides auto-detection of available Ollama models so integration tests
use the smallest local model instead of hardcoding cloud-only models.
"""

import json
import urllib.request
import urllib.error

import pytest

# IMPORTANT: Use 127.0.0.1, NOT localhost.
# On macOS, localhost may resolve to ::1 (IPv6) which hits a different
# Ollama instance with no models loaded.
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_OPENAI_URL = f"{OLLAMA_BASE_URL}/v1"

# Models known to lack tool-calling support
_NO_TOOL_SUPPORT_FAMILIES = {"gemma3", "bert", "nomic-bert"}


def _get_ollama_models():
    """Query Ollama for available local chat models, sorted by size (smallest first).

    Excludes embedding models, cloud-only models, and models without tool support.
    Returns list of (name, size_bytes) tuples.
    """
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []

    models = []
    for m in data.get("models", []):
        name = m.get("name", "")
        size = m.get("size", 0)
        family = m.get("details", {}).get("family", "")

        # Skip embedding models
        if family.lower() in _NO_TOOL_SUPPORT_FAMILIES:
            continue
        # Skip cloud-only models (size < 1MB means remote stub)
        if size < 1_000_000:
            continue
        # Skip models without tool support (gemma3 family)
        if any(name.startswith(prefix) for prefix in _NO_TOOL_SUPPORT_FAMILIES):
            continue

        models.append((name, size))

    return sorted(models, key=lambda x: x[1])


def get_smallest_ollama_model():
    """Return the name of the smallest available Ollama model, or None."""
    models = _get_ollama_models()
    return models[0][0] if models else None


def ollama_available():
    """Check if Ollama has at least one usable model."""
    return bool(_get_ollama_models())


@pytest.fixture
def ollama_model():
    """Fixture providing the smallest available Ollama model name.

    Skips the test if no Ollama models are available.
    """
    model = get_smallest_ollama_model()
    if model is None:
        pytest.skip("No Ollama models available at 127.0.0.1:11434")
    return model

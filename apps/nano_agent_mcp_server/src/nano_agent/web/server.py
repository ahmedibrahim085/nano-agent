"""
Nano-Agent Web UI — FastAPI backend.

Serves the dashboard HTML and provides REST API endpoints for:
- Provider health checks
- Model catalog
- Agent prompt execution
- Execution history
- Configuration management
- Agent config editor
"""

import glob as globmod
import os
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import uvicorn

from ..modules.constants import (
    PROVIDER_REQUIREMENTS,
    AVAILABLE_MODELS,
    ZAI_BASE_URL,
    ZAI_AVAILABLE_MODELS,
    LMSTUDIO_BASE_URL,
    QWEN_BASE_URL,
    QWEN_AVAILABLE_MODELS,
    MODEL_INFO,
)
from ..modules.qwen_auth import QWEN_CREDS_PATH
from ..modules.nano_agent import prompt_nano_agent

logger = logging.getLogger(__name__)

app = FastAPI(title="Nano-Agent Dashboard", version="1.0.0")

# --- In-memory execution history ---
execution_history: list[dict] = []
MAX_HISTORY = 100

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8484",
        "http://127.0.0.1:8484",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- Models ---

class RunRequest(BaseModel):
    prompt: str
    model: str
    provider: str
    workspace: str = ""


class ConfigUpdate(BaseModel):
    key: str
    value: str


class AgentConfig(BaseModel):
    name: str
    content: str


# --- Provider Health ---

LOCAL_PROVIDERS = {
    "ollama": {
        "url": "http://127.0.0.1:11434",
        "health": "/api/tags",
        "extract": lambda d: [m["name"] for m in d.get("models", [])],
    },
    "lmstudio": {
        "url": LMSTUDIO_BASE_URL,
        "health": "/v1/models",
        "extract": lambda d: [m["id"] for m in d.get("data", [])],
    },
}


def _check_local_provider(name: str, config: dict) -> dict:
    """Check health of a local provider (Ollama/LM Studio)."""
    start = time.time()
    try:
        resp = requests.get(f"{config['url']}{config['health']}", timeout=3)
        latency = round((time.time() - start) * 1000)
        models = config["extract"](resp.json())
        return {
            "name": name,
            "status": "online",
            "latency_ms": latency,
            "model_count": len(models),
            "models": models,
            "base_url": config["url"],
            "type": "local",
        }
    except Exception:
        return {
            "name": name,
            "status": "offline",
            "latency_ms": None,
            "model_count": 0,
            "models": [],
            "base_url": config["url"],
            "type": "local",
        }


def _check_cloud_provider(name: str, env_key: Optional[str], models: list, base_url: str) -> dict:
    """Check health of a cloud provider by API key presence."""
    has_key = env_key is None or bool(os.getenv(env_key))
    return {
        "name": name,
        "status": "online" if has_key else "no_api_key",
        "latency_ms": None,
        "model_count": len(models),
        "models": models,
        "base_url": base_url,
        "type": "cloud",
    }


# --- Endpoints ---

@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/providers")
async def get_providers():
    providers = []

    # Local providers — check connectivity
    for name, config in LOCAL_PROVIDERS.items():
        providers.append(_check_local_provider(name, config))

    # Cloud providers — check API key presence
    providers.append(_check_cloud_provider(
        "openai", "OPENAI_API_KEY",
        AVAILABLE_MODELS.get("openai", []),
        "https://api.openai.com/v1",
    ))
    providers.append(_check_cloud_provider(
        "anthropic", "ANTHROPIC_API_KEY",
        AVAILABLE_MODELS.get("anthropic", []),
        "https://api.anthropic.com/v1",
    ))
    providers.append(_check_cloud_provider(
        "zai", "Z_AI_API_KEY",
        ZAI_AVAILABLE_MODELS,
        ZAI_BASE_URL,
    ))
    # Qwen Cloud: file-based OAuth, not env-var-based — check creds file directly
    providers.append({
        "name": "qwen",
        "status": "online" if QWEN_CREDS_PATH.exists() else "no_api_key",
        "latency_ms": None,
        "model_count": len(QWEN_AVAILABLE_MODELS),
        "models": QWEN_AVAILABLE_MODELS,
        "base_url": QWEN_BASE_URL,
        "type": "cloud",
    })

    return {"providers": providers}


@app.get("/api/models")
async def get_models():
    all_models = []

    # Local providers — query live
    for name, config in LOCAL_PROVIDERS.items():
        try:
            resp = requests.get(f"{config['url']}{config['health']}", timeout=3)
            models = config["extract"](resp.json())
            for m in models:
                all_models.append({
                    "name": m,
                    "provider": name,
                    "type": "local",
                    "description": MODEL_INFO.get(m, ""),
                    "status": "available",
                })
        except Exception:
            pass

    # Cloud providers — static lists
    for provider, models in AVAILABLE_MODELS.items():
        env_key = PROVIDER_REQUIREMENTS.get(provider)
        has_key = env_key is None or bool(os.getenv(env_key))
        for m in models:
            all_models.append({
                "name": m,
                "provider": provider,
                "type": "cloud",
                "description": MODEL_INFO.get(m, ""),
                "status": "available" if has_key else "no_api_key",
            })

    # Z.ai
    has_zai = bool(os.getenv("Z_AI_API_KEY"))
    for m in ZAI_AVAILABLE_MODELS:
        all_models.append({
            "name": m,
            "provider": "zai",
            "type": "cloud",
            "description": MODEL_INFO.get(m, f"Z.ai {m}"),
            "status": "available" if has_zai else "no_api_key",
        })

    # Qwen Cloud
    has_qwen = QWEN_CREDS_PATH.exists()
    for m in QWEN_AVAILABLE_MODELS:
        all_models.append({
            "name": m,
            "provider": "qwen",
            "type": "cloud",
            "description": MODEL_INFO.get(m, f"Qwen {m}"),
            "status": "available" if has_qwen else "no_api_key",
        })

    return {"models": all_models}


@app.post("/api/run")
async def run_agent(req: RunRequest):
    try:
        result = await prompt_nano_agent(
            agentic_prompt=req.prompt,
            model=req.model,
            provider=req.provider,
            workspace=req.workspace,
        )
        # Save to history
        entry = {
            "id": len(execution_history) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": req.prompt,
            "model": req.model,
            "provider": req.provider,
            "success": result.get("success", False),
            "result": result.get("result"),
            "error": result.get("error"),
            "execution_time_seconds": result.get("execution_time_seconds"),
            "token_usage": result.get("metadata", {}).get("token_usage"),
        }
        execution_history.insert(0, entry)
        if len(execution_history) > MAX_HISTORY:
            execution_history.pop()
        return result
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": str(e),
            "metadata": {},
            "execution_time_seconds": None,
        }


# --- Feature 4: Execution History ---

@app.get("/api/history")
async def get_history():
    return {"history": execution_history}


@app.delete("/api/history")
async def clear_history():
    execution_history.clear()
    return {"cleared": True}


# --- Feature 5: Configuration Manager ---

AGENT_CONFIG_DIR = Path.home() / ".claude" / "agents"
ENV_FILE = Path(__file__).parents[4] / ".env"


def _mask_key(value: str) -> str:
    """Mask API key showing only last 4 chars."""
    if not value or len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


@app.get("/api/config")
async def get_config():
    """Return current configuration with masked API keys."""
    config = {}
    for provider, env_key in PROVIDER_REQUIREMENTS.items():
        if env_key is None:
            config[provider] = {"env_key": None, "status": "not_required"}
        else:
            value = os.getenv(env_key, "")
            config[provider] = {
                "env_key": env_key,
                "is_set": bool(value),
                "masked_value": _mask_key(value) if value else "",
                "status": "configured" if value else "missing",
            }
    return {"config": config, "env_file": str(ENV_FILE)}


@app.put("/api/config")
async def update_config(update: ConfigUpdate):
    """Update an environment variable (runtime only)."""
    allowed_keys = {v for v in PROVIDER_REQUIREMENTS.values() if v is not None}
    if update.key not in allowed_keys:
        raise HTTPException(400, f"Cannot update key: {update.key}")
    os.environ[update.key] = update.value
    return {"updated": update.key, "status": "ok"}


# --- Feature 6: Agent Config Editor ---

@app.get("/api/agents")
async def list_agents():
    """List all nano-agent config files."""
    pattern = str(AGENT_CONFIG_DIR / "nano-agent-*.md")
    agents = []
    for filepath in sorted(globmod.glob(pattern)):
        p = Path(filepath)
        content = p.read_text()
        agents.append({
            "name": p.stem,
            "filename": p.name,
            "path": str(p),
            "size": p.stat().st_size,
            "content": content,
        })
    return {"agents": agents}


@app.get("/api/agents/{name}")
async def get_agent(name: str):
    """Read a single agent config."""
    filepath = AGENT_CONFIG_DIR / f"{name}.md"
    if not filepath.exists():
        raise HTTPException(404, f"Agent config not found: {name}")
    return {"name": name, "content": filepath.read_text(), "path": str(filepath)}


@app.put("/api/agents/{name}")
async def update_agent(name: str, config: AgentConfig):
    """Create or update an agent config file."""
    if not name.startswith("nano-agent-"):
        raise HTTPException(400, "Agent name must start with 'nano-agent-'")
    filepath = AGENT_CONFIG_DIR / f"{name}.md"
    filepath.write_text(config.content)
    return {"name": name, "status": "saved", "path": str(filepath)}


@app.delete("/api/agents/{name}")
async def delete_agent(name: str):
    """Delete an agent config file."""
    filepath = AGENT_CONFIG_DIR / f"{name}.md"
    if not filepath.exists():
        raise HTTPException(404, f"Agent config not found: {name}")
    filepath.unlink()
    return {"name": name, "status": "deleted"}


def main():
    """Entry point for the web UI server."""
    print("\n  Nano-Agent Dashboard")
    print("  http://localhost:8484\n")
    uvicorn.run(app, host="0.0.0.0", port=8484, log_level="warning")


if __name__ == "__main__":
    main()

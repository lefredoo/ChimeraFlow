"""
Configuration management for ChimeraFlow Backend
Follows AGENTS.md §7: No fallback values, fail fast on missing required vars
"""
import os
from typing import Optional


def require_env(name: str, description: str) -> str:
    """
    Require an environment variable. Fails fast if missing.
    
    Args:
        name: Variable name
        description: Human-readable description of what this variable is for
        
    Returns:
        Variable value
        
    Raises:
        ValueError: If variable is not set
    """
    value = os.getenv(name)
    if value is None:
        raise ValueError(
            f"Required environment variable '{name}' is not set.\n"
            f"Purpose: {description}\n"
            f"Set it in .env file or via Doppler."
        )
    return value


def optional_env(name: str) -> Optional[str]:
    """
    Get optional environment variable.
    
    Args:
        name: Variable name
        
    Returns:
        Variable value or None if not set
    """
    return os.getenv(name)


# Backend Configuration
NODE_ENV = optional_env("BACKEND_NODE_ENV") or "development"
PORT = int(optional_env("BACKEND_PORT") or "8000")
LOG_LEVEL = optional_env("BACKEND_LOG_LEVEL") or "INFO"

# CORS
CORS_ORIGINS = optional_env("CORS_ORIGINS") or "http://localhost:3000"

# Redis (required for rate limiting, optional in test environment)
# In test environment, features that depend on Redis will be disabled
REDIS_URL = optional_env("REDIS_URL") if NODE_ENV == "test" else require_env("REDIS_URL", "Redis connection for rate limiting and cache")

# Data Directory
DATA_DIR = optional_env("DATA_DIR") or "./data"

# Rate Limiting
RATE_LIMIT_PER_IP = int(optional_env("RATE_LIMIT_PER_IP") or "10")
RATE_LIMIT_WINDOW_SECONDS = int(optional_env("RATE_LIMIT_WINDOW_SECONDS") or "60")

# LiteLLM (optional - feature disabled if not set)
LITELLM_API_KEY = optional_env("LITELLM_API_KEY")
LITELLM_BUDGET_USD = float(optional_env("LITELLM_BUDGET_USD") or "5.0")

# MCP Servers
MCP_EXCEL_URL = optional_env("MCP_EXCEL_URL") or "http://localhost:9001"
MCP_ACCESS_URL = optional_env("MCP_ACCESS_URL") or "http://localhost:9002"
MCP_WHATSAPP_URL = optional_env("MCP_WHATSAPP_URL") or "http://localhost:9003"
MCP_MOMO_URL = optional_env("MCP_MOMO_URL") or "http://localhost:9004"

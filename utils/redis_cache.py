"""Shared async Redis cache module.

Both admin_server.py (Next.js API) and server.py (WhatsApp MCP) import from here.
All operations are safe-fail: a Redis outage never breaks a request.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── TTL constants (seconds) ───────────────────────────────────────────────────
CACHE_TTL_PROPERTIES_LIST = 60    # admin list endpoint (agency-scoped)
CACHE_TTL_PROPERTY_DETAIL = 120   # single property detail (shared key)
CACHE_TTL_SEARCH = 30             # public customer-facing search results

# ── Singleton client ──────────────────────────────────────────────────────────
_redis_client: Optional[aioredis.Redis] = None


def _build_client() -> Optional[aioredis.Redis]:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return aioredis.from_url(redis_url, decode_responses=True)

    host = os.getenv("REDIS_HOST")
    port = os.getenv("REDIS_PORT")
    password = os.getenv("REDIS_PASSWORD")

    if host and port and password:
        ssl = os.getenv("REDIS_SSL", "false").lower() == "true"
        return aioredis.Redis(
            host=host,
            port=int(port),
            decode_responses=True,
            username=os.getenv("REDIS_USERNAME", "default"),
            password=password,
            ssl=ssl,
            socket_connect_timeout=3,
            socket_timeout=2,
        )

    return None


def _get_client() -> Optional[aioredis.Redis]:
    """Return the module-level singleton, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = _build_client()
    return _redis_client


def disable_redis(reason: str, exc: Exception) -> None:
    """Called on any Redis error to disable caching for this process lifetime."""
    global _redis_client
    logger.warning("Redis disabled (%s): %s", reason, exc)
    _redis_client = None


# ── Lifecycle helpers ─────────────────────────────────────────────────────────

async def ping_redis() -> bool:
    """Ping Redis at startup. Returns True if healthy, disables on failure."""
    client = _get_client()
    if client is None:
        logger.info("Redis not configured — caching disabled.")
        return False
    try:
        await client.ping()
        logger.info("Redis connected.")
        return True
    except Exception as exc:
        disable_redis("startup ping", exc)
        return False


async def close_redis() -> None:
    """Graceful shutdown — close the connection pool."""
    client = _get_client()
    if client:
        try:
            await client.aclose()
        except Exception:
            pass


# ── Core safe helpers ─────────────────────────────────────────────────────────

async def redis_get_safe(key: str) -> Optional[str]:
    client = _get_client()
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception as exc:
        disable_redis("get", exc)
        return None


async def redis_setex_safe(key: str, ttl_seconds: int, value: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        await client.setex(key, ttl_seconds, value)
    except Exception as exc:
        disable_redis("setex", exc)


async def redis_delete_safe(key: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception as exc:
        disable_redis("delete", exc)


async def redis_invalidate_pattern(pattern: str) -> None:
    """SCAN + bulk DELETE all keys matching a glob pattern."""
    client = _get_client()
    if client is None:
        return
    try:
        keys = [k async for k in client.scan_iter(match=pattern, count=100)]
        if keys:
            await client.delete(*keys)
    except Exception as exc:
        disable_redis("invalidate_pattern", exc)


# ── Cache key builders ────────────────────────────────────────────────────────

def property_list_cache_key(agency_id: str, role: str, **filters) -> str:
    """Agency-scoped list key used by admin_server.py."""
    canonical = json.dumps(
        {"agency_id": agency_id, "role": role, **filters},
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha1(canonical.encode()).hexdigest()
    return f"properties:list:{agency_id}:{digest}"


def property_detail_cache_key(property_id: str) -> str:
    """Shared detail key — same key used by both admin & MCP servers."""
    return f"property:detail:{property_id}"


def property_search_cache_key(**filters) -> str:
    """Global (non-agency) search key used by server.py (customer-facing)."""
    canonical = json.dumps(filters, sort_keys=True, default=str)
    digest = hashlib.sha1(canonical.encode()).hexdigest()
    return f"properties:search:{digest}"

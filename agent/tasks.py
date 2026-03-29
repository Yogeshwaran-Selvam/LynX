"""
Background task runner using ThreadPoolExecutor.
I/O-bound work (GitHub API + Groq API) — threads are ideal.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

logger = logging.getLogger(__name__)

_pool = None


def _get_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        size = getattr(settings, "LYNX_THREAD_POOL_SIZE", 3)
        _pool = ThreadPoolExecutor(max_workers=size, thread_name_prefix="lynx")
    return _pool


def submit(fn, *args, **kwargs):
    """Submit a task to the background thread pool."""
    future = _get_pool().submit(fn, *args, **kwargs)
    future.add_done_callback(_log_result)
    return future


def _log_result(future):
    exc = future.exception()
    if exc:
        logger.error(f"Background task failed: {exc}", exc_info=exc)
    else:
        logger.info("Background task completed")

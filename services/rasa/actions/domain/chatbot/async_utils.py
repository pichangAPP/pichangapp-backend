from __future__ import annotations

import asyncio
from functools import partial
from typing import Any


def run_in_thread(function: Any, *args: Any, **kwargs: Any) -> Any:
    """Ejecuta una funcion bloqueante en un thread del loop actual."""
    loop = asyncio.get_running_loop()
    bound = partial(function, *args, **kwargs)
    return loop.run_in_executor(None, bound)

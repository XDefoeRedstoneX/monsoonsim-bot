"""Bridge between Tkinter's main loop and asyncio.

Tkinter is not thread-safe, so rather than running asyncio on a background
thread we cooperatively pump the Tk event loop from inside a single asyncio
loop. Playwright's async API only needs *an* event loop running, which this
provides, while all widget access stays on the main thread.
"""
from __future__ import annotations

import asyncio


def create_event_loop() -> asyncio.AbstractEventLoop:
    """Create and install a fresh event loop (avoids the deprecated
    ``asyncio.get_event_loop()`` which errors on Python 3.12+)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


async def pump_tk(app, interval: float = 0.05) -> None:
    """Drive Tk's ``update()`` until the window is destroyed."""
    import tkinter as tk

    while True:
        try:
            app.update()
        except tk.TclError:
            break
        await asyncio.sleep(interval)

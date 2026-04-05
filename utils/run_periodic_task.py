import asyncio

async def run_periodic_task(coro, interval_seconds: int):
    """
    Run an async coroutine periodically.
    
    coro: an async function with no arguments
    interval_seconds: time between runs in seconds
    """
    while True:
        try:
            await coro()
        except Exception as e:
            print(f"Error in background task: {e}")
        await asyncio.sleep(interval_seconds)

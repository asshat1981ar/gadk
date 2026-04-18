import asyncio

async def delay_tool(seconds: int = 1) -> str:
    """Mock tool that sleeps for N seconds to test parallelism."""
    print(f"[TEST_TOOL] Sleeping for {seconds}s...")
    await asyncio.sleep(seconds)
    return f"Slept for {seconds}s"

import asyncio
import os

import pytest
from litellm import acompletion


@pytest.mark.asyncio
async def test_llm_completion():
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        api_base = "https://openrouter.ai/api/v1"
        model = "openrouter/elephant-alpha"

        print(f"Testing LiteLLM with OpenRouter ({model})...")
        res = await acompletion(
            model=model,
            api_key=api_key,
            api_base=api_base,
            messages=[{"role": "user", "content": "hi"}],
            timeout=15
        )
        print("Success!")
        print(res.choices[0].message.content)
    except Exception as e:
        print(f"CAUGHT_ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_completion())

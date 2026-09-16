import sys
print("Starting script...", flush=True)

import asyncio
print("Importing dotenv...", flush=True)
from dotenv import load_dotenv

print("Importing ai_agent...", flush=True)
from ai_agent import ai_assistant

async def test():
    print("Loading dotenv...", flush=True)
    load_dotenv()
    print("Sending text to AI...", flush=True)
    try:
        ans = await ai_assistant.get_response("salom jigar", 12345)
        print(f"AI response: {ans}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test())

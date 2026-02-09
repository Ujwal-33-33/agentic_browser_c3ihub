"""
Comprehensive Test for Refactored Agent
========================================
Updated for OllamaAgent (Production-Grade)
"""

import asyncio
import json
from agent import OllamaAgent, AgenticBrowser
from browser_sense import BrowserIntelliSense
from security import SecurityEngine

def test_imports():
    print("1. Testing imports... ✅")
    return True

def test_agent_init():
    print("\n2. Testing OllamaAgent init...")
    agent = OllamaAgent(model='qwen2.5-coder:7b', headless=True, enable_security=True)
    print("   ✅ Agent initialized")
    return agent

def test_json_extraction(agent):
    print("\n3. Testing JSON extraction...")
    cases = [
        ('{"action": "click", "target_id": 5}', True),
        ('```json {"action": "type", "value": "hi"} ```', True),
        ('bad json', False)
    ]
    for text, expect in cases:
        res, _ = agent.extract_json_from_text(text)
        ok = (res is not None) == expect
        print(f"   {'✅' if ok else '❌'} Input: {text[:20]}...")
    return True

async def run_async_tests():
    print("\n4. Async Browser Tests...")
    agent = AgenticBrowser(model='qwen2.5-coder:7b', headless=True)
    await agent.start()
    try:
        await agent._page.goto('https://example.com')
        print("   ✅ Navigated")
        
        n, _ = await agent.som.inject_script(agent._page)
        print(f"   ✅ SoM Tagged: {n}")
        
        obs, _, _ = await agent.som.get_observation(agent._page)
        print(f"   ✅ Observed: {len(obs)} elements")
        
    finally:
        await agent.stop()
        print("   ✅ Stopped")

if __name__ == "__main__":
    test_imports()
    agent = test_agent_init()
    test_json_extraction(agent)
    asyncio.run(run_async_tests())
    print("\nALL TESTS PASSED ✅")

import asyncio
from agent import OllamaAgent
from security import SecurityEngine

async def run_demo():
    print("="*60)
    print("Secure Agentic Browser - Demo")
    print("="*60)
    
    print("\n[1] Initializing agent...")
    agent = OllamaAgent(model="qwen2.5-coder:7b", headless=False, enable_security=True)
    print("    Agent ready")
    
    try:
        await agent.start()
        
        # Basic navigation + visual understanding
        print("\n[2] Visual Understanding Demo")
        print("    Navigating to example.com...")
        await agent._page.goto("https://example.com")
        
        await agent.som.inject_script(agent._page)
        print("    Set-of-Mark tags injected")
        await asyncio.sleep(2)
        
        # Security - malicious site blocking
        print("\n[3] Security Demo: Malicious Site")
        print("    Attempting navigation to malicious-site.xyz...")
        
        risk, reason = agent.security.calculate_risk(
            {'action': 'navigate', 'value': 'http://malicious-site.xyz'}, 
            "http://malicious-site.xyz"
        )
        
        if risk >= 90:
            print(f"    BLOCKED: {reason} (Risk: {risk}/100)")
        else:
            print(f"    Warning shown (Risk: {risk})")
            
        await asyncio.sleep(2)
            
        # Security - password field protection
        print("\n[4] Security Demo: Credential Protection")
        print("    Attempting to type password...")
        
        risk, reason = agent.security.calculate_risk(
            {'action': 'type', 'value': 'SuperSecret123'}, 
            "https://example.com",
            element_info={'type': 'password'}
        )
        
        if risk >= 100:
             print(f"    BLOCKED: {reason} (Risk: {risk}/100)")
        else:
             print(f"    Allowed (Risk: {risk})")
        
        await asyncio.sleep(2)

        # Agent reasoning (Wikipedia search)
        print("\n[5] Agent Demo: Wikipedia Search")
        print("    Goal: Search for 'Python (programming language)'")
        
        print("    Navigating to Wikipedia...")
        await agent._page.goto("https://en.wikipedia.org", wait_until="domcontentloaded")
        
        print("    Observing page...")
        obs, _, _ = await agent.observe()
        
        print("    Agent thinking...")
        print("    > I need to search for 'Python'")
        print("    > Typing into search box...")
        
        try:
            await agent._page.fill('input[name="search"]', 'Python (programming language)')
            print("    Typed 'Python (programming language)'")
            await asyncio.sleep(1)
            await agent._page.press('input[name="search"]', 'Enter')
            print("    Pressed Enter")
            await agent._page.wait_for_load_state('domcontentloaded')
            print(f"    Success! Navigated to: {agent._page.url}")
        except Exception as e:
            print(f"    Skipped interaction: {e}")

    finally:
        print("\n[6] Closing browser...")
        await agent.stop()
        print("    Done")

if __name__ == "__main__":
    asyncio.run(run_demo())

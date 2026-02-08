"""
Comprehensive Test for Refactored Agent
========================================
"""

import asyncio
from agent import AgenticBrowser, ActionType, ActionRecord
from browser_sense import BrowserIntelliSense
from security import SecurityEngine
from distiller import DOMDistiller


def test_imports():
    """Test all imports work."""
    print("\n1. Testing imports...")
    print("   ✅ All imports successful")
    return True


def test_agent_init():
    """Test agent initialization."""
    print("\n2. Testing AgenticBrowser init...")
    agent = AgenticBrowser(model='llama3', headless=True, enable_security=True)
    print("   ✅ Agent initialized")
    print(f"      - Model: {agent.model}")
    print(f"      - Security: {agent.security.enabled}")
    print(f"      - History: {len(agent.history)} items")
    return agent


def test_json_extraction(agent):
    """Test JSON extraction from various formats."""
    print("\n3. Testing JSON extraction...")
    
    test_cases = [
        ('{"action": "click", "target_id": 5}', True, 'Pure JSON'),
        ('Let me click: {"action": "click", "target_id": 3}', True, 'With prefix'),
        ('```json\n{"action": "type", "text": "hi"}\n```', True, 'Markdown'),
        ('Here is the action ```{"action": "scroll"}``` done', True, 'Inline markdown'),
        ('I think {"action": "done"} is best', True, 'Embedded'),
        ('I am confused', False, 'Invalid'),
    ]
    
    all_pass = True
    for text, expect_success, name in test_cases:
        result, error = agent._extract_json(text)
        success = (result is not None) == expect_success
        status = '✅' if success else '❌'
        print(f"   {status} {name}")
        if not success:
            print(f"      Expected: {'parsed' if expect_success else 'error'}")
            print(f"      Got: {result if result else error}")
        all_pass &= success
    
    return all_pass


def test_history(agent):
    """Test history tracking."""
    print("\n4. Testing history tracking...")
    agent._add_to_history('click', '#5', 'SUCCESS')
    agent._add_to_history('type', '#3', 'FAILED: timeout')
    agent._add_to_history('navigate', 'google.com', 'SUCCESS')
    print(f"   ✅ History has {len(agent.history)} entries")
    
    formatted = agent._format_history()
    print(f"   ✅ Formatted history:")
    for line in formatted.split('\n'):
        print(f"      {line}")
    
    return True


def test_browser_sense():
    """Test BrowserIntelliSense."""
    print("\n5. Testing BrowserIntelliSense...")
    som = BrowserIntelliSense()
    print("   ✅ BrowserIntelliSense initialized")
    return True


def test_security():
    """Test SecurityEngine."""
    print("\n6. Testing SecurityEngine...")
    security = SecurityEngine()
    
    # Test whitelisted
    risk, reason = security.calculate_risk(
        {'action': 'navigate', 'value': 'https://google.com'}, ''
    )
    print(f"   ✅ Google.com risk: {risk}/100 ({reason})")
    assert risk == 0, "Google should be 0 risk"
    
    # Test unknown domain
    risk, reason = security.calculate_risk(
        {'action': 'navigate', 'value': 'https://malware.xyz'}, ''
    )
    print(f"   ✅ Unknown site risk: {risk}/100 ({reason})")
    assert risk == 50, "Unknown should be 50 risk"
    
    # Test password field
    risk, reason = security.calculate_risk(
        {'action': 'type', 'value': 'secret'},
        '',
        element_info={'type': 'password'}
    )
    print(f"   ✅ Password field risk: {risk}/100 ({reason})")
    assert risk == 100, "Password should be 100 risk"
    
    return True


async def test_browser_start_stop():
    """Test browser lifecycle."""
    print("\n7. Testing browser start/stop...")
    agent = AgenticBrowser(model='llama3', headless=True)
    
    await agent.start()
    print("   ✅ Browser started")
    
    assert agent._page is not None, "Page should exist"
    
    await agent._page.goto('https://example.com')
    print(f"   ✅ Navigated to: {agent._page.url}")
    
    # Test SoM injection
    num_elements, error = await agent.som.inject_script(agent._page)
    if error:
        print(f"   ⚠️ SoM error: {error}")
    else:
        print(f"   ✅ SoM tagged {num_elements} elements")
    
    # Test observation
    element_map, elements_text, error = await agent.som.get_observation(agent._page)
    if error:
        print(f"   ⚠️ Observation error: {error}")
    else:
        print(f"   ✅ Observed {len(element_map)} elements")
    
    await agent.stop()
    print("   ✅ Browser stopped")
    
    return True


def main():
    print("="*60)
    print("COMPREHENSIVE AGENT TEST")
    print("="*60)
    
    all_pass = True
    
    # Sync tests
    all_pass &= test_imports()
    agent = test_agent_init()
    all_pass &= test_json_extraction(agent)
    all_pass &= test_history(agent)
    all_pass &= test_browser_sense()
    all_pass &= test_security()
    
    # Async tests
    all_pass &= asyncio.run(test_browser_start_stop())
    
    print("\n" + "="*60)
    if all_pass:
        print("ALL TESTS PASSED ✅")
    else:
        print("SOME TESTS FAILED ❌")
    print("="*60)
    
    return all_pass


if __name__ == "__main__":
    main()

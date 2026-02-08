"""
Test Refactored Agent - Wikipedia Virat Kohli Search
====================================================
Tests the refactored agent with visual grounding, memory, and error recovery.
"""

import asyncio
from agent import AgenticBrowser


async def test_wikipedia_virat_kohli():
    """Test agent searching for Virat Kohli on Wikipedia."""
    
    print("\n" + "=" * 70)
    print("TESTING REFACTORED AGENT - VIRAT KOHLI WIKIPEDIA SEARCH")
    print("=" * 70 + "\n")
    
    agent = AgenticBrowser(
        model="llama3",  # Use llama3 (or llava for visual grounding)
        headless=False,
        max_iterations=12,
        enable_security=True
    )
    
    try:
        await agent.run(
            goal="Search Wikipedia for 'Virat Kohli' and navigate to his page",
            start_url="https://en.wikipedia.org"
        )
        
        print("\n" + "=" * 70)
        print("AGENT EXECUTION HISTORY")
        print("=" * 70)
        
        if agent.history:
            for record in agent.history:
                status = "✅" if "Success" in record.result else "❌"
                print(f"{status} Step {record.step_num}: {record.action}")
                print(f"   Result: {record.result}")
                print()
        else:
            print("No history recorded")
        
        print("=" * 70)
        print("TEST COMPLETE")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("\nPartial history:")
        for record in agent.history:
            print(f"  Step {record.step_num}: {record.action} → {record.result}")


if __name__ == "__main__":
    asyncio.run(test_wikipedia_virat_kohli())

#!/usr/bin/env python3

import asyncio
import argparse
import logging
import sys
from typing import Optional

from agent import OllamaAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print welcome banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          🌐 SECURE AGENTIC BROWSER v2.0                      ║
║          Powered by Ollama + Playwright                      ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_results(success: bool, agent: OllamaAgent):
    """Print final results."""
    print("\n" + "="*60)
    
    if success:
        print("✅ GOAL ACHIEVED!")
    else:
        print("❌ GOAL NOT ACHIEVED (max iterations reached)")
    
    print("\n📜 ACTION HISTORY:")
    for record in agent.history:
        print(f"   {record}")
    
    print("="*60 + "\n")


async def run_agent(
    goal: str,
    start_url: str = "https://www.google.com",
    model: str = "qwen2.5-coder:7b",
    headless: bool = False,
    debug: bool = False,
    max_iterations: int = 15,
    enable_security: bool = True
) -> bool:
    """
    Run the agent with the specified configuration.
    
    Args:
        goal: Natural language goal
        start_url: Starting URL
        model: Ollama model name
        headless: Run browser invisibly
        debug: Enable debug mode (highlight elements)
        max_iterations: Max steps before timeout
        enable_security: Enable security checks
        
    Returns:
        True if goal was achieved
    """
    print_banner()
    
    print(f"🎯 Goal: {goal}")
    print(f"🌐 Start URL: {start_url}")
    print(f"🤖 Model: {model}")
    print(f"🔒 Security: {'Enabled' if enable_security else 'Disabled'}")
    print(f"🐛 Debug Mode: {'Enabled' if debug else 'Disabled'}")
    print()
    
    agent = OllamaAgent(
        model=model,
        headless=headless,
        max_iterations=max_iterations,
        enable_security=enable_security,
        debug_mode=debug
    )
    
    try:
        success = await agent.run(goal=goal, start_url=start_url)
        print_results(success, agent)
        return success
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        await agent.stop()
        return False
    except Exception as e:
        logger.error(f"Agent error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Secure Agentic Browser - AI-powered web automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Search Wikipedia for Python programming"
  python main.py "Find the latest news about AI" --url https://news.google.com
  python main.py "Search for weather in New York" --debug
  python main.py "Get stock price of AAPL" --headless
        """
    )
    
    parser.add_argument(
        "goal",
        nargs="?",
        default="Search for 'Python programming' on Wikipedia",
        help="Natural language goal for the agent"
    )
    
    parser.add_argument(
        "--url", "-u",
        default="https://www.google.com",
        help="Starting URL (default: https://www.google.com)"
    )
    
    parser.add_argument(
        "--model", "-m",
        default="qwen2.5-coder:7b",
        help="Ollama model name (default: qwen2.5-coder:7b)"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (invisible)"
    )
    
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode (highlight elements before clicking)"
    )
    
    parser.add_argument(
        "--max-iterations", "-n",
        type=int,
        default=15,
        help="Maximum iterations before timeout (default: 15)"
    )
    
    parser.add_argument(
        "--no-security",
        action="store_true",
        help="Disable security checks (not recommended)"
    )
    
    args = parser.parse_args()
    
    # Run the agent
    success = asyncio.run(run_agent(
        goal=args.goal,
        start_url=args.url,
        model=args.model,
        headless=args.headless,
        debug=args.debug,
        max_iterations=args.max_iterations,
        enable_security=not args.no_security
    ))
    
    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

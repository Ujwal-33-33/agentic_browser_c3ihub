"""
Ollama-Powered Agentic Browser
===============================
A browser automation agent using local Ollama LLM with Playwright.
Architecture: Observe -> Think -> Act loop with security middleware.

Author: Secure Agentic Browser Project
"""

import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from openai import AsyncOpenAI
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# System prompt for LLM - forces structured JSON output
SYSTEM_PROMPT = """You are a browser automation agent. Your task is to analyze the current state of a web page and determine the next action to take.

You will receive:
1. The text content of the page (DOM text)
2. The current URL and title
3. The user's goal

Based on this information, you must respond with ONLY a valid JSON object in the following format:
{
    "thought": "Your reasoning about what to do next",
    "action": "click" | "type" | "navigate" | "scroll" | "wait" | "done",
    "selector": "CSS selector for the element (required for click/type)",
    "value": "Text to type (required for type) or URL (for navigate) or scroll amount in pixels (for scroll)"
}

Action types:
- "click": Click on an element. Requires "selector".
- "type": Type text into an input field. Requires "selector" and "value".
- "navigate": Navigate to a URL. Requires "value" with the URL.
- "scroll": Scroll the page. Optional "value" for scroll amount in pixels (default: 500).
- "wait": Wait for page to load. Optional "value" for seconds (default: 1).
- "done": Indicate that the goal has been achieved.

Rules:
1. Always respond with valid JSON only - no markdown, no explanation outside JSON.
2. Use precise CSS selectors that will uniquely identify the target element.
3. Consider the current state before deciding the action.
4. If the goal is achieved, use action "done".
5. Be methodical and take one action at a time.
6. CRITICAL: Your response must be pure JSON. Do not wrap it in markdown code blocks.
"""


# =============================================================================
# ACTION TYPES AND DATA STRUCTURES
# =============================================================================

class ActionType(Enum):
    """Supported browser actions."""
    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    WAIT = "wait"
    DONE = "done"


@dataclass
class AgentAction:
    """Represents an action the agent wants to perform."""
    action_type: ActionType
    thought: str
    selector: Optional[str] = None
    value: Optional[str] = None

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "AgentAction":
        """Parse action from JSON/dict format."""
        action_str = json_data.get("action", "").lower()
        return cls(
            action_type=ActionType(action_str),
            thought=json_data.get("thought", ""),
            selector=json_data.get("selector"),
            value=json_data.get("value"),
        )

    def to_json(self) -> Dict[str, Any]:
        """Convert action to JSON/dict format."""
        result = {
            "action": self.action_type.value,
            "thought": self.thought,
        }
        if self.selector:
            result["selector"] = self.selector
        if self.value:
            result["value"] = self.value
        return result


@dataclass
class Observation:
    """Represents the observed state of the browser."""
    url: str
    title: str
    text_content: str
    screenshot_base64: str


@dataclass
class SecurityResult:
    """Result from a security check."""
    is_safe: bool
    reason: str


# =============================================================================
# SECURITY LAYER CLASS (PLACEHOLDER)
# =============================================================================

class SecurityLayer:
    """
    Security middleware for the agentic browser.
    
    Provides two critical security checkpoints:
    1. scan_observation: Analyze page content for malicious payloads
    2. validate_action: Validate LLM-proposed actions before execution
    
    NOTE: Security logic is left as placeholder - implement as needed.
    """

    def __init__(self) -> None:
        self.enabled = True
        logger.info("SecurityLayer initialized")

    def scan_observation(self, observation: Observation) -> SecurityResult:
        """
        Scan the observation (DOM/text content) for malicious payloads.
        
        This method is called BEFORE the observation is sent to the LLM.
        Implement detection for:
        - Prompt injection attacks
        - Malicious scripts or hidden content
        - Suspicious iframes or redirects
        
        Args:
            observation: The current browser observation
            
        Returns:
            SecurityResult: Contains is_safe and reason
        """
        if not self.enabled:
            return SecurityResult(is_safe=True, reason="Security checks disabled")

        # ======================================================================
        # TODO: Implement observation scanning logic
        # 
        # Example patterns to detect:
        # - "Ignore previous instructions"
        # - Hidden text with CSS tricks
        # - Base64 encoded payloads
        # - Unusual Unicode characters
        # ======================================================================

        logger.debug("Observation scan complete - no threats detected (placeholder)")
        return SecurityResult(
            is_safe=True,
            reason="Observation scan passed (security logic not implemented)"
        )

    def validate_action(self, action: Dict[str, Any]) -> SecurityResult:
        """
        Validate an action proposed by the LLM before execution.
        
        This method is called AFTER the LLM proposes an action but BEFORE
        it is executed. Implement validation for:
        - Blocking navigation to malicious URLs
        - Preventing credential theft
        - Enforcing action allowlists
        
        Args:
            action: The action dictionary proposed by the LLM
            
        Returns:
            SecurityResult: Contains is_safe and reason
        """
        if not self.enabled:
            return SecurityResult(is_safe=True, reason="Security checks disabled")

        # ======================================================================
        # TODO: Implement action validation logic
        # 
        # Example checks:
        # - URL reputation for navigate actions
        # - Block sensitive field inputs (password, credit card)
        # - Action rate limiting
        # ======================================================================

        action_type = action.get("action", "unknown")
        logger.debug(f"Action validation complete - action allowed (placeholder): {action_type}")
        return SecurityResult(
            is_safe=True,
            reason="Action validation passed (security logic not implemented)"
        )


# =============================================================================
# OLLAMA AGENT CLASS
# =============================================================================

class OllamaAgent:
    """
    Main agent class that orchestrates the Observe -> Think -> Act loop
    using local Ollama LLM.
    """

    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        max_iterations: int = 50,
        model_name: str = OLLAMA_MODEL,
    ) -> None:
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.max_iterations = max_iterations
        self.model_name = model_name

        # Initialize security layer
        self.security = SecurityLayer()

        # Initialize Ollama client (OpenAI-compatible)
        self.client = AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",  # Ollama doesn't require a real API key
        )

        # Browser components (initialized in start)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Action history
        self.action_history: list = []

        logger.info(f"OllamaAgent initialized (model={model_name}, headless={headless}, max_iterations={max_iterations})")

    async def start(self) -> None:
        """Start the browser."""
        logger.info("Starting browser...")

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-features=VizDisplayCompositor",
                "--no-sandbox",
            ]
        )

        self._context = await self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )

        self._page = await self._context.new_page()

        logger.info(f"Browser started (headless={self.headless})")

    async def stop(self) -> None:
        """Stop the browser and cleanup resources."""
        logger.info("Stopping browser...")

        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        logger.info("Browser stopped")

    async def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        logger.info(f"Navigating to: {url}")
        await self._page.goto(url, wait_until="domcontentloaded")

    async def _observe(self) -> Observation:
        """
        Observe the current state of the browser.
        
        Returns:
            Observation: Screenshot + text content of the page
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        # Get screenshot as base64
        screenshot_bytes = await self._page.screenshot()
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Get text content of the page
        text_content = await self._page.evaluate("() => document.body.innerText")

        return Observation(
            url=self._page.url,
            title=await self._page.title(),
            text_content=text_content[:10000],  # Limit text content
            screenshot_base64=screenshot_base64,
        )

    async def _think(self, observation: Observation, goal: str) -> Dict[str, Any]:
        """
        Send observation to Ollama LLM and get the next action.
        
        Args:
            observation: Current browser observation
            goal: The user's goal
            
        Returns:
            Dict containing the action specification
        """
        # Build the prompt
        prompt_text = f"""
Current URL: {observation.url}
Page Title: {observation.title}

User Goal: {goal}

Page Text Content (DOM):
{observation.text_content}

Based on the page content above, determine the next action to achieve the goal.
Respond with a valid JSON object only.
"""

        # TODO: Switch model to 'llava' to re-enable screenshot understanding.
        # For text-only models like llama3, we only send DOM text content.
        
        # Prepare messages for OpenAI-compatible API
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ]

        # Send to Ollama via OpenAI-compatible endpoint
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
            )
            
            response_text = response.choices[0].message.content
            
            # Try to extract JSON if wrapped in markdown code blocks
            if "```json" in response_text:
                # Extract JSON from markdown
                import re
                json_match = re.search(r'```json\s*({.*?})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif "```" in response_text:
                # Extract from generic code block
                import re
                json_match = re.search(r'```\s*({.*?})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            # Parse JSON response
            action_json = json.loads(response_text.strip())
            return action_json
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            raise ValueError(f"Invalid JSON response from LLM: {response_text}")
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            raise

    async def _act(self, action: AgentAction) -> bool:
        """
        Execute an action in the browser.
        
        Args:
            action: The action to execute
            
        Returns:
            bool: True if action succeeded, False otherwise
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            match action.action_type:
                case ActionType.CLICK:
                    if not action.selector:
                        raise ValueError("Click action requires a selector")
                    await self._page.click(action.selector, timeout=5000)
                    logger.info(f"Clicked: {action.selector}")

                case ActionType.TYPE:
                    if not action.selector or not action.value:
                        raise ValueError("Type action requires selector and value")
                    await self._page.fill(action.selector, action.value)
                    logger.info(f"Typed into: {action.selector}")

                case ActionType.NAVIGATE:
                    if not action.value:
                        raise ValueError("Navigate action requires a URL")
                    await self.navigate(action.value)
                    logger.info(f"Navigated to: {action.value}")

                case ActionType.SCROLL:
                    scroll_amount = int(action.value) if action.value else 500
                    await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    logger.info(f"Scrolled by: {scroll_amount}px")

                case ActionType.WAIT:
                    wait_time = float(action.value) if action.value else 1.0
                    await asyncio.sleep(wait_time)
                    logger.info(f"Waited: {wait_time}s")

                case ActionType.DONE:
                    logger.info("Agent signaled completion")
                    return True

                case _:
                    logger.warning(f"Unknown action type: {action.action_type}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False

    async def run(self, url: str, goal: str) -> Tuple[bool, str]:
        """
        Run the agent loop to achieve the given goal.
        
        Args:
            url: Starting URL
            goal: The goal to achieve (natural language)
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        logger.info(f"Agent starting - Goal: {goal}")
        logger.info(f"Starting URL: {url}")

        try:
            await self.start()
            await self.navigate(url)

            iteration = 0

            # Main agent loop: Observe -> Think -> Act
            while iteration < self.max_iterations:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"ITERATION {iteration}/{self.max_iterations}")
                logger.info(f"{'='*60}")

                # ==========================================
                # STEP 1: OBSERVE
                # ==========================================
                logger.info("STEP 1: Observing browser state...")
                observation = await self._observe()
                logger.info(f"  URL: {observation.url}")
                logger.info(f"  Title: {observation.title}")
                logger.info(f"  Text length: {len(observation.text_content)} chars")

                # ==========================================
                # SECURITY CHECK 1: Scan observation
                # ==========================================
                logger.info("SECURITY CHECK 1: Scanning observation...")
                scan_result = self.security.scan_observation(observation)

                if not scan_result.is_safe:
                    error_msg = f"SECURITY ABORT: Observation scan failed - {scan_result.reason}"
                    logger.error(error_msg)
                    return (False, error_msg)

                logger.info(f"  Scan result: SAFE - {scan_result.reason}")

                # ==========================================
                # STEP 2: THINK (Send to Ollama LLM)
                # ==========================================
                logger.info("STEP 2: Consulting Ollama LLM for next action...")
                try:
                    action_json = await self._think(observation, goal)
                except ValueError as e:
                    logger.error(f"Failed to get valid action from Ollama: {e}")
                    continue

                logger.info(f"  LLM proposed: {json.dumps(action_json, indent=2)}")
                logger.info(f"  Thought: {action_json.get('thought', 'N/A')}")

                # ==========================================
                # SECURITY CHECK 2: Validate action
                # ==========================================
                logger.info("SECURITY CHECK 2: Validating proposed action...")
                validation_result = self.security.validate_action(action_json)

                if not validation_result.is_safe:
                    error_msg = f"SECURITY ABORT: Action validation failed - {validation_result.reason}"
                    logger.error(error_msg)
                    return (False, error_msg)

                logger.info(f"  Validation result: SAFE - {validation_result.reason}")

                # ==========================================
                # STEP 3: ACT
                # ==========================================
                logger.info("STEP 3: Executing action...")

                try:
                    action = AgentAction.from_json(action_json)
                except (ValueError, KeyError) as e:
                    logger.error(f"Failed to parse action: {e}")
                    continue

                # Check if agent signals completion
                if action.action_type == ActionType.DONE:
                    logger.info("Agent signaled goal completion!")
                    return (True, f"Goal achieved: {action.thought}")

                # Execute the action
                success = await self._act(action)

                if success:
                    self.action_history.append(action_json)
                    logger.info("  Action executed successfully")
                else:
                    logger.warning("  Action execution failed, continuing...")

                # Small delay to allow page to update
                await asyncio.sleep(0.5)

            # Max iterations reached
            return (False, f"Max iterations ({self.max_iterations}) reached without completing goal")

        except Exception as e:
            error_msg = f"Agent error: {e}"
            logger.exception(error_msg)
            return (False, error_msg)

        finally:
            await self.stop()

    def reset(self) -> None:
        """Reset the agent's history for a new task."""
        self.action_history = []
        logger.info("Agent history reset")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main() -> None:
    """Example usage of the Ollama-Powered Agentic Browser."""
    print("\n" + "=" * 70)
    print("OLLAMA-POWERED AGENTIC BROWSER")
    print("=" * 70 + "\n")

    # Create agent
    agent = OllamaAgent(
        headless=False,  # Set to True for headless operation
        viewport_width=1280,
        viewport_height=720,
        max_iterations=10,
    )

    # Example: Run the agent
    success, message = await agent.run(
        url="https://example.com",
        goal="Find and click on the 'More information' link on the page"
    )

    print("\n" + "=" * 70)
    print(f"RESULT: {'SUCCESS' if success else 'FAILURE'}")
    print(f"Message: {message}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

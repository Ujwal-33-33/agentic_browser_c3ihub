"""
Secure Agentic Browser Framework
================================
A modular, extensible browser agent using Playwright (async) and a mock LLM interface.
Architecture: Observe -> Think -> Act loop with security middleware.

Author: For Cybersecurity Challenge
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Any, Dict

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    SCREENSHOT = "screenshot"
    DONE = "done"


@dataclass
class AgentAction:
    """Represents an action the agent wants to perform."""
    action_type: ActionType
    selector: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'AgentAction':
        """Parse action from JSON/dict format."""
        action_str = json_data.get("action", "").lower()
        return cls(
            action_type=ActionType(action_str),
            selector=json_data.get("selector"),
            value=json_data.get("value"),
            url=json_data.get("url")
        )
    
    def to_json(self) -> Dict[str, Any]:
        """Convert action to JSON/dict format."""
        result = {"action": self.action_type.value}
        if self.selector:
            result["selector"] = self.selector
        if self.value:
            result["value"] = self.value
        if self.url:
            result["url"] = self.url
        return result


@dataclass
class SecurityResult:
    """Result from a security check."""
    is_safe: bool
    reason: str
    threat_type: Optional[str] = None
    confidence: float = 1.0


@dataclass
class BrowserState:
    """Represents the current state of the browser."""
    url: str
    title: str
    dom_content: str
    accessibility_tree: Optional[Dict[str, Any]] = None
    screenshot_base64: Optional[str] = None


# =============================================================================
# BROWSER MANAGER CLASS
# =============================================================================

class BrowserManager:
    """
    Handles Playwright startup, context creation, and page navigation.
    Provides methods for browser control and state observation.
    """
    
    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        user_agent: Optional[str] = None
    ):
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.user_agent = user_agent
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        logger.info("BrowserManager initialized")
    
    async def start(self) -> None:
        """Start the browser and create a new context/page."""
        logger.info("Starting browser...")
        
        self._playwright = await async_playwright().start()
        
        # Launch browser with security-conscious settings
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-web-security',  # Note: Enable for testing only
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
            ]
        )
        
        # Create context with specified viewport
        context_options = {
            "viewport": {
                "width": self.viewport_width,
                "height": self.viewport_height
            }
        }
        if self.user_agent:
            context_options["user_agent"] = self.user_agent
        
        self._context = await self._browser.new_context(**context_options)
        self._page = await self._context.new_page()
        
        logger.info(f"Browser started (headless={self.headless})")
    
    async def stop(self) -> None:
        """Close the browser and cleanup resources."""
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
    
    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        logger.info(f"Navigating to: {url}")
        await self._page.goto(url, wait_until=wait_until)
    
    async def get_dom_snapshot(self) -> str:
        """
        Get the current DOM/HTML content of the page.
        
        Returns:
            str: The HTML content of the current page.
        
        Note: This is a critical observation point. The returned content
        should be scanned for malicious payloads before processing.
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        # Get the full HTML content
        html_content = await self._page.content()
        return html_content
    
    async def get_accessibility_tree(self) -> Dict[str, Any]:
        """
        Get the accessibility tree snapshot of the page.
        
        This provides a structured representation of interactive elements
        which can be safer to process than raw HTML.
        
        Returns:
            Dict: Accessibility tree snapshot
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        # Get accessibility snapshot
        snapshot = await self._page.accessibility.snapshot()
        return snapshot or {}
    
    async def get_browser_state(self) -> BrowserState:
        """
        Get the complete current state of the browser.
        
        Returns:
            BrowserState: Object containing URL, title, DOM, and accessibility tree.
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        return BrowserState(
            url=self._page.url,
            title=await self._page.title(),
            dom_content=await self.get_dom_snapshot(),
            accessibility_tree=await self.get_accessibility_tree()
        )
    
    async def execute_action(self, action: AgentAction) -> bool:
        """
        Execute a browser action.
        
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
                    await self._page.click(action.selector)
                    logger.info(f"Clicked: {action.selector}")
                
                case ActionType.TYPE:
                    if not action.selector or not action.value:
                        raise ValueError("Type action requires selector and value")
                    await self._page.fill(action.selector, action.value)
                    logger.info(f"Typed into: {action.selector}")
                
                case ActionType.NAVIGATE:
                    if not action.url:
                        raise ValueError("Navigate action requires a URL")
                    await self.navigate(action.url)
                    logger.info(f"Navigated to: {action.url}")
                
                case ActionType.SCROLL:
                    # Scroll down by default, or use value for specific scroll amount
                    scroll_amount = int(action.value) if action.value else 500
                    await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    logger.info(f"Scrolled by: {scroll_amount}px")
                
                case ActionType.WAIT:
                    wait_time = float(action.value) if action.value else 1.0
                    await asyncio.sleep(wait_time)
                    logger.info(f"Waited: {wait_time}s")
                
                case ActionType.SCREENSHOT:
                    path = action.value or "screenshot.png"
                    await self._page.screenshot(path=path)
                    logger.info(f"Screenshot saved: {path}")
                
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
    
    @property
    def page(self) -> Optional[Page]:
        """Get the current page object for advanced operations."""
        return self._page


# =============================================================================
# SECURITY LAYER CLASS
# =============================================================================

class SecurityLayer:
    """
    Security middleware for the agentic browser.
    
    This class provides two critical security checkpoints:
    1. scan_observation: Analyze DOM content for malicious payloads
    2. validate_action: Validate LLM-proposed actions before execution
    
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║  IMPORTANT: This is where you implement your security logic!          ║
    ║  The methods below are placeholders - add your detection algorithms   ║
    ║  for prompt injection, XSS, malicious redirects, etc.                 ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self):
        # Configuration for security checks
        self.enabled = True
        self.strict_mode = False  # If True, block on any suspicion
        
        # ==================================================================
        # TODO: Initialize your security components here
        # Examples:
        # - Prompt injection detection model
        # - XSS pattern matchers
        # - URL reputation database
        # - Action allowlist/blocklist
        # ==================================================================
        
        logger.info("SecurityLayer initialized")
    
    def scan_observation(self, dom_content: str) -> SecurityResult:
        """
        Scan the DOM content for malicious payloads.
        
        This method is called BEFORE the DOM content is sent to the LLM.
        Use this to detect and block:
        - Prompt injection attacks embedded in web pages
        - Malicious scripts or hidden content
        - Suspicious iframes or redirects
        - Data exfiltration attempts
        
        Args:
            dom_content: The raw HTML/DOM content from the page
            
        Returns:
            SecurityResult: Contains is_safe (bool) and reason (str)
        
        ╔═══════════════════════════════════════════════════════════════════╗
        ║  IMPLEMENT YOUR OBSERVATION SCANNING LOGIC HERE                   ║
        ╚═══════════════════════════════════════════════════════════════════╝
        """
        
        if not self.enabled:
            return SecurityResult(is_safe=True, reason="Security checks disabled")
        
        # ==================================================================
        # TODO: Implement prompt injection detection
        # 
        # Example patterns to look for:
        # - "Ignore previous instructions"
        # - "You are now..."
        # - Hidden text with font-size: 0 or visibility: hidden
        # - Base64 encoded payloads
        # - Unusual Unicode characters
        #
        # Example implementation:
        # 
        # injection_patterns = [
        #     r"ignore\s+(all\s+)?previous\s+instructions",
        #     r"you\s+are\s+now\s+a",
        #     r"disregard\s+your\s+programming",
        #     r"new\s+instructions:",
        # ]
        # 
        # for pattern in injection_patterns:
        #     if re.search(pattern, dom_content, re.IGNORECASE):
        #         return SecurityResult(
        #             is_safe=False,
        #             reason=f"Prompt injection detected: {pattern}",
        #             threat_type="PROMPT_INJECTION"
        #         )
        # ==================================================================
        
        # ==================================================================
        # TODO: Implement XSS/Script detection
        #
        # Look for:
        # - Suspicious script tags
        # - Event handlers with malicious code
        # - Data URIs with JavaScript
        # ==================================================================
        
        # ==================================================================
        # TODO: Implement hidden content detection
        #
        # Look for:
        # - CSS hiding techniques (display:none containing instructions)
        # - Zero-width characters
        # - White text on white background
        # ==================================================================
        
        # Placeholder: Currently allows all content
        logger.debug("Observation scan complete - no threats detected (placeholder)")
        return SecurityResult(
            is_safe=True,
            reason="Observation scan passed (security logic not implemented)"
        )
    
    def validate_action(self, action_json: Dict[str, Any]) -> SecurityResult:
        """
        Validate an action proposed by the LLM before execution.
        
        This method is called AFTER the LLM proposes an action but BEFORE
        it is executed. Use this to:
        - Block navigation to malicious URLs
        - Prevent credential theft (blocking input to certain fields)
        - Detect prompt injection in action payloads
        - Enforce action allowlists
        
        Args:
            action_json: The action in dictionary format
            
        Returns:
            SecurityResult: Contains is_safe (bool) and reason (str)
        
        ╔═══════════════════════════════════════════════════════════════════╗
        ║  IMPLEMENT YOUR ACTION VALIDATION LOGIC HERE                      ║
        ╚═══════════════════════════════════════════════════════════════════╝
        """
        
        if not self.enabled:
            return SecurityResult(is_safe=True, reason="Security checks disabled")
        
        action_type = action_json.get("action", "").lower()
        selector = action_json.get("selector", "")
        value = action_json.get("value", "")
        url = action_json.get("url", "")
        
        # ==================================================================
        # TODO: Implement URL reputation checking for navigate actions
        #
        # Example:
        # if action_type == "navigate":
        #     if is_malicious_url(url):
        #         return SecurityResult(
        #             is_safe=False,
        #             reason=f"Blocked navigation to malicious URL: {url}",
        #             threat_type="MALICIOUS_URL"
        #         )
        # ==================================================================
        
        # ==================================================================
        # TODO: Implement sensitive field protection
        #
        # Block typing into password fields, credit card fields, etc.
        # unless explicitly allowed by the goal.
        #
        # Example:
        # sensitive_selectors = ["#password", "#credit-card", "#ssn"]
        # if action_type == "type" and any(s in selector for s in sensitive_selectors):
        #     return SecurityResult(
        #         is_safe=False,
        #         reason=f"Blocked input to sensitive field: {selector}",
        #         threat_type="SENSITIVE_DATA"
        #     )
        # ==================================================================
        
        # ==================================================================
        # TODO: Implement action payload inspection
        #
        # Check if the action's value contains malicious content
        # that might be used for XSS or code injection.
        # ==================================================================
        
        # ==================================================================
        # TODO: Implement action rate limiting
        #
        # Detect and block action loops or excessive actions
        # that might indicate the agent is being manipulated.
        # ==================================================================
        
        # Placeholder: Currently allows all actions
        logger.debug(f"Action validation complete - action allowed (placeholder): {action_type}")
        return SecurityResult(
            is_safe=True,
            reason="Action validation passed (security logic not implemented)"
        )
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable security checks."""
        self.enabled = enabled
        logger.info(f"Security layer {'enabled' if enabled else 'disabled'}")
    
    def set_strict_mode(self, strict: bool) -> None:
        """
        Set strict mode.
        
        In strict mode, any suspicion results in blocking.
        In normal mode, only high-confidence threats are blocked.
        """
        self.strict_mode = strict
        logger.info(f"Strict mode {'enabled' if strict else 'disabled'}")


# =============================================================================
# LLM INTERFACE (MOCK)
# =============================================================================

class LLMInterface(ABC):
    """Abstract base class for LLM interfaces."""
    
    @abstractmethod
    async def get_next_action(
        self,
        goal: str,
        browser_state: BrowserState,
        history: list
    ) -> Dict[str, Any]:
        """
        Get the next action from the LLM.
        
        Args:
            goal: The user's goal
            browser_state: Current browser state
            history: List of previous actions
            
        Returns:
            Dict containing the action specification
        """
        pass


class MockLLM(LLMInterface):
    """
    Mock LLM for testing the agent framework.
    
    Replace this with actual LLM integration (LangChain, OpenAI, etc.)
    for production use.
    """
    
    def __init__(self):
        self.action_sequence = [
            {"action": "click", "selector": "button#login"},
            {"action": "type", "selector": "input#username", "value": "testuser"},
            {"action": "type", "selector": "input#password", "value": "testpass"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "done"}
        ]
        self.current_index = 0
    
    async def get_next_action(
        self,
        goal: str,
        browser_state: BrowserState,
        history: list
    ) -> Dict[str, Any]:
        """Return a fixed sequence of actions for testing."""
        
        # ==================================================================
        # TODO: Replace with actual LLM call
        #
        # Example with LangChain:
        # 
        # from langchain.chat_models import ChatOpenAI
        # from langchain.schema import HumanMessage, SystemMessage
        #
        # llm = ChatOpenAI(model="gpt-4", temperature=0)
        # 
        # prompt = f"""
        # You are a browser automation agent.
        # Goal: {goal}
        # Current URL: {browser_state.url}
        # Page Title: {browser_state.title}
        # 
        # Available actions: click, type, navigate, scroll, wait, done
        # 
        # Respond with a JSON action, e.g.:
        # {{"action": "click", "selector": "button#submit"}}
        # """
        # 
        # response = await llm.agenerate([[HumanMessage(content=prompt)]])
        # return json.loads(response.generations[0][0].text)
        # ==================================================================
        
        if self.current_index >= len(self.action_sequence):
            return {"action": "done"}
        
        action = self.action_sequence[self.current_index]
        self.current_index += 1
        
        logger.info(f"Mock LLM returning action: {action}")
        return action


# =============================================================================
# AGENT CLASS
# =============================================================================

class Agent:
    """
    The main agent that orchestrates the Observe -> Think -> Act loop.
    
    This agent:
    1. Observes the current browser state
    2. Passes observations through security scanning
    3. Asks the LLM for the next action
    4. Validates the action through security checks
    5. Executes the action
    
    The loop continues until the goal is achieved or an error/threat occurs.
    """
    
    def __init__(
        self,
        browser_manager: BrowserManager,
        security_layer: SecurityLayer,
        llm: LLMInterface,
        max_iterations: int = 50
    ):
        self.browser = browser_manager
        self.security = security_layer
        self.llm = llm
        self.max_iterations = max_iterations
        self.action_history: list = []
        
        logger.info(f"Agent initialized (max_iterations={max_iterations})")
    
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
            # Start browser and navigate to initial URL
            await self.browser.start()
            await self.browser.navigate(url)
            
            iteration = 0
            
            # Main agent loop: Observe -> Think -> Act
            while iteration < self.max_iterations:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"ITERATION {iteration}/{self.max_iterations}")
                logger.info(f"{'='*60}")
                
                # ==========================================
                # STEP 1: OBSERVE - Get current browser state
                # ==========================================
                logger.info("STEP 1: Observing browser state...")
                browser_state = await self.browser.get_browser_state()
                logger.info(f"  URL: {browser_state.url}")
                logger.info(f"  Title: {browser_state.title}")
                logger.info(f"  DOM size: {len(browser_state.dom_content)} chars")
                
                # ==========================================
                # STEP 2: SECURITY - Scan observation
                # ==========================================
                logger.info("STEP 2: Scanning observation for threats...")
                scan_result = self.security.scan_observation(browser_state.dom_content)
                
                if not scan_result.is_safe:
                    error_msg = f"SECURITY ABORT: Observation scan failed - {scan_result.reason}"
                    logger.error(error_msg)
                    if scan_result.threat_type:
                        logger.error(f"  Threat type: {scan_result.threat_type}")
                    return (False, error_msg)
                
                logger.info(f"  Scan result: SAFE - {scan_result.reason}")
                
                # ==========================================
                # STEP 3: THINK - Get action from LLM
                # ==========================================
                logger.info("STEP 3: Consulting LLM for next action...")
                action_json = await self.llm.get_next_action(
                    goal=goal,
                    browser_state=browser_state,
                    history=self.action_history
                )
                logger.info(f"  LLM proposed action: {json.dumps(action_json)}")
                
                # ==========================================
                # STEP 4: SECURITY - Validate action
                # ==========================================
                logger.info("STEP 4: Validating proposed action...")
                validation_result = self.security.validate_action(action_json)
                
                if not validation_result.is_safe:
                    error_msg = f"SECURITY ABORT: Action validation failed - {validation_result.reason}"
                    logger.error(error_msg)
                    if validation_result.threat_type:
                        logger.error(f"  Threat type: {validation_result.threat_type}")
                    return (False, error_msg)
                
                logger.info(f"  Validation result: SAFE - {validation_result.reason}")
                
                # ==========================================
                # STEP 5: ACT - Execute the action
                # ==========================================
                logger.info("STEP 5: Executing action...")
                
                try:
                    action = AgentAction.from_json(action_json)
                except (ValueError, KeyError) as e:
                    logger.error(f"Failed to parse action: {e}")
                    continue
                
                # Check if agent signals completion
                if action.action_type == ActionType.DONE:
                    logger.info("Agent signaled goal completion!")
                    return (True, "Goal achieved successfully")
                
                # Execute the action
                success = await self.browser.execute_action(action)
                
                if success:
                    self.action_history.append(action_json)
                    logger.info(f"  Action executed successfully")
                else:
                    logger.warning(f"  Action execution failed, continuing...")
                
                # Small delay to allow page to update
                await asyncio.sleep(0.5)
            
            # Max iterations reached
            return (False, f"Max iterations ({self.max_iterations}) reached without completing goal")
            
        except Exception as e:
            error_msg = f"Agent error: {e}"
            logger.exception(error_msg)
            return (False, error_msg)
        
        finally:
            # Always cleanup
            await self.browser.stop()
    
    def reset(self) -> None:
        """Reset the agent's history for a new task."""
        self.action_history = []
        logger.info("Agent history reset")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """
    Example usage of the Secure Agentic Browser.
    """
    print("\n" + "="*70)
    print("SECURE AGENTIC BROWSER FRAMEWORK")
    print("="*70 + "\n")
    
    # Initialize components
    browser_manager = BrowserManager(
        headless=False,  # Set to True for headless operation
        viewport_width=1280,
        viewport_height=720
    )
    
    security_layer = SecurityLayer()
    # security_layer.set_strict_mode(True)  # Uncomment for strict security
    
    llm = MockLLM()  # Replace with real LLM for production
    
    # Create agent
    agent = Agent(
        browser_manager=browser_manager,
        security_layer=security_layer,
        llm=llm,
        max_iterations=10
    )
    
    # Run the agent
    # Example: Navigate to a page and perform actions
    success, message = await agent.run(
        url="https://example.com",
        goal="Navigate to the login page and enter test credentials"
    )
    
    print("\n" + "="*70)
    print(f"RESULT: {'SUCCESS' if success else 'FAILURE'}")
    print(f"Message: {message}")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

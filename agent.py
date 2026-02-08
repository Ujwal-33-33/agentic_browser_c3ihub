"""
Ollama-Powered Agentic Browser - Secured with SecurityEngine
==============================================================
A robust browser automation agent with:
- Visual grounding (llava vision model support)
- Short-term memory (last 5 steps)
- Robust error recovery
- Full Security Layer Integration

Security Features:
- Prompt injection prevention (sanitize_and_wrap)
- Risk calculation (Iron Gate logic)
- Deceptive UI detection
- Domain whitelisting

Author: Secure Agentic Browser Project
"""

import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

# Import SecurityEngine
from security import SecurityEngine

# Load environment variables
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# System prompt with history awareness
SYSTEM_PROMPT_TEMPLATE = """You are a browser automation agent with visual grounding and memory.

**HISTORY CONTEXT:**
{history_context}

**YOUR TASK:**
Analyze the current state and determine the next action. If the previous step failed, try a different approach.

**OUTPUT FORMAT (JSON ONLY):**
{{
    "thought": "Your reasoning about what to do next",
    "action": "click" | "type" | "navigate" | "scroll" | "wait" | "done",
    "selector": "CSS selector (required for click/type)",
    "value": "Text to type or URL to navigate or scroll pixels"
}}

**ACTION TYPES:**
- "click": Click element (requires selector)
- "type": Type text (requires selector + value)
- "navigate": Go to URL (requires value)
- "scroll": Scroll page (optional value for pixels)
- "wait": Wait for load (optional value for seconds)
- "done": Goal achieved

**CRITICAL RULES:**
1. Pure JSON output only - no markdown, no extra text
2. Use precise CSS selectors
3. If previous action failed, try different selector/approach
4. Review history to avoid repeating failed actions
5. One action at a time
6. Use "done" when goal is achieved
"""


# =============================================================================
# DATA STRUCTURES
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
        """Parse action from JSON."""
        action_str = json_data.get("action", "").lower()
        try:
            action_type = ActionType(action_str)
        except ValueError:
            action_type = ActionType.WAIT

        return cls(
            action_type=action_type,
            thought=json_data.get("thought", ""),
            selector=json_data.get("selector"),
            value=json_data.get("value")
        )


@dataclass
class StepRecord:
    """Record of a single step for short-term memory."""
    step_num: int
    action: str
    result: str  # "Success" or "Failed: <error>"


# =============================================================================
# AGENTIC BROWSER
# =============================================================================

class AgenticBrowser:
    """
    Browser agent with visual grounding, memory, error recovery, and security.
    """
    
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        headless: bool = False,
        max_iterations: int = 15,
        enable_security: bool = True
    ):
        """
        Initialize the agentic browser.
        
        Args:
            model: LLM model name (e.g., "llama3", "llava")
            headless: Run browser in headless mode
            max_iterations: Maximum steps before timeout
            enable_security: Enable security layer
        """
        self.model = model
        self.headless = headless
        self.max_iterations = max_iterations
        
        # Short-term memory: last 5 steps
        self.history: List[StepRecord] = []
        
        # Ollama client
        self.client = AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama"
        )
        
        # ===== SECURITY ENGINE =====
        self.security = SecurityEngine(enabled=enable_security)
        
        # Browser state
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        logger.info(f"AgenticBrowser initialized with model: {model}")
        logger.info(f"Security: {'ENABLED' if enable_security else 'DISABLED'}")
    
    async def start(self):
        """Start the browser."""
        logger.info("Starting browser...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        logger.info("Browser started successfully")
    
    async def stop(self):
        """Stop the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")
    
    async def _capture_screenshot(self, page: Page) -> Optional[str]:
        """Capture screenshot and return base64 encoded string."""
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=50)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None
    
    def _format_history(self) -> str:
        """Format history for LLM context."""
        if not self.history:
            return "No previous steps."
        
        lines = []
        for record in self.history[-5:]:
            lines.append(f"Step {record.step_num}: {record.action} → {record.result}")
        return "\n".join(lines)
    
    async def _get_element_info(self, page: Page, selector: str) -> Optional[Dict]:
        """Get element information for security checks."""
        try:
            element = await page.query_selector(selector)
            if not element:
                return None
            
            info = await page.evaluate("""(selector) => {
                const el = document.querySelector(selector);
                if (!el) return null;
                return {
                    tag: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    text: (el.innerText || el.value || '').slice(0, 100),
                    href: el.getAttribute('href') || ''
                };
            }""", selector)
            
            return info
        except Exception:
            return None
    
    async def _query_llm(
        self,
        user_goal: str,
        page_state_text: str,
        screenshot_base64: Optional[str],
        current_url: str,
        last_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query the LLM with SECURE page state (sanitized).
        """
        # Format history context
        history_context = self._format_history()
        
        # Build system prompt with history
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            history_context=history_context
        )
        
        # ===== SECURITY: Sanitize page state =====
        # Wrap page content to prevent prompt injection
        secured_state = self.security.sanitize_and_wrap(page_state_text)
        
        # Build user message with sanitized content
        user_message_parts = [
            f"**USER GOAL:** {user_goal}",
            f"**CURRENT URL:** {current_url}",
            ""
        ]
        
        if last_error:
            user_message_parts.append(f"**PREVIOUS ERROR:** {last_error}")
            user_message_parts.append("")
        
        # Add sanitized page state
        user_message_parts.append("**PAGE STATE (Sandboxed Data):**")
        user_message_parts.append(json.dumps(secured_state, indent=2)[:3000])
        
        user_message_text = "\n".join(user_message_parts)
        
        # Build messages for API
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Visual grounding for vision models
        is_vision_model = "llava" in self.model.lower() or "vision" in self.model.lower()
        
        if is_vision_model and screenshot_base64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{screenshot_base64}"
                        }
                    }
                ]
            })
            logger.info("Using visual grounding with screenshot")
        else:
            messages.append({
                "role": "user",
                "content": user_message_text
            })
        
        # Query LLM
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"LLM response: {response_text[:200]}")
            
            # Parse JSON
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {"action": "wait", "thought": "JSON parse error", "value": "2"}
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            return {"action": "wait", "thought": f"LLM error: {e}", "value": "2"}
    
    async def execute_safe_action(
        self,
        page: Page,
        action_plan: AgentAction,
        element_map: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """Execute action with error recovery."""
        try:
            action_type = action_plan.action_type
            
            if action_type == ActionType.NAVIGATE:
                if not action_plan.value:
                    return False, "Error: Navigate requires URL value"
                await page.goto(action_plan.value, wait_until="domcontentloaded", timeout=10000)
                await page.wait_for_timeout(1000)
                return True, f"Navigated to {action_plan.value}"
            
            elif action_type == ActionType.CLICK:
                if not action_plan.selector:
                    return False, "Error: Click requires selector"
                await page.click(action_plan.selector, timeout=5000)
                await page.wait_for_timeout(500)
                return True, f"Clicked {action_plan.selector}"
            
            elif action_type == ActionType.TYPE:
                if not action_plan.selector or not action_plan.value:
                    return False, "Error: Type requires selector and value"
                await page.fill(action_plan.selector, action_plan.value, timeout=5000)
                await page.wait_for_timeout(300)
                return True, f"Typed '{action_plan.value}' into {action_plan.selector}"
            
            elif action_type == ActionType.SCROLL:
                scroll_amount = int(action_plan.value) if action_plan.value else 500
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                await page.wait_for_timeout(500)
                return True, f"Scrolled {scroll_amount}px"
            
            elif action_type == ActionType.WAIT:
                wait_time = int(action_plan.value) if action_plan.value else 1
                await page.wait_for_timeout(wait_time * 1000)
                return True, f"Waited {wait_time}s"
            
            elif action_type == ActionType.DONE:
                return True, "Goal achieved"
            
            else:
                return False, f"Error: Unknown action type {action_type}"
        
        except PlaywrightTimeoutError as e:
            return False, f"Timeout: {str(e)[:100]}"
        except Exception as e:
            return False, f"Error: {str(e)[:100]}"
    
    def _request_user_approval(self, action: Dict, risk: int, reason: str) -> bool:
        """Request user approval for high-risk actions."""
        print("\n" + "="*70)
        print("⚠️  SECURITY GATE - USER APPROVAL REQUIRED")
        print("="*70)
        print(f"Risk Level: {risk}/100")
        print(f"Action: {action.get('action', 'unknown').upper()}")
        if action.get('value'):
            print(f"Target: {action.get('value')}")
        if action.get('selector'):
            print(f"Element: {action.get('selector')}")
        print(f"Reason: {reason}")
        print("="*70)
        
        try:
            response = input("⚠️ Authorize this action? (y/n): ").strip().lower()
            return response in ['y', 'yes']
        except EOFError:
            logger.warning("Non-interactive mode, denying high-risk action")
            return False
    
    async def run(self, goal: str, start_url: str = "https://www.google.com"):
        """
        Run the agentic browser to achieve the goal.
        
        Implements IRON GATE security logic:
        - Risk >= 90: BLOCK (automatic denial)
        - Risk >= 40: PAUSE (user approval required)
        - Risk < 40: PROCEED (automatic approval)
        """
        logger.info(f"Starting agent with goal: {goal}")
        
        await self.start()
        
        try:
            # Navigate to start URL
            await self._page.goto(start_url, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(2000)
            
            current_url = start_url
            last_error = None
            
            for iteration in range(self.max_iterations):
                logger.info(f"\n{'='*70}")
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
                logger.info(f"{'='*70}")
                
                # ============================================================
                # OBSERVE
                # ============================================================
                logger.info("OBSERVE: Capturing page state...")
                
                screenshot_base64 = await self._capture_screenshot(self._page)
                
                page_text = await self._page.evaluate("() => document.body.innerText")
                page_state = page_text[:5000]
                
                new_url = self._page.url
                if new_url != current_url:
                    logger.info(f"SYSTEM NOTE: Navigation occurred ({current_url} → {new_url})")
                    page_state = f"[NAVIGATION OCCURRED]\n{page_state}"
                    current_url = new_url
                
                # ============================================================
                # THINK (with sanitized input)
                # ============================================================
                logger.info("THINK: Querying LLM (with sanitized input)...")
                
                action_json = await self._query_llm(
                    user_goal=goal,
                    page_state_text=page_state,
                    screenshot_base64=screenshot_base64,
                    current_url=current_url,
                    last_error=last_error
                )
                
                action = AgentAction.from_json(action_json)
                logger.info(f"Thought: {action.thought}")
                logger.info(f"Action: {action.action_type.value}")
                
                if action.action_type == ActionType.DONE:
                    logger.info("✅ Agent reports goal achieved!")
                    self.history.append(StepRecord(
                        step_num=iteration + 1,
                        action="DONE",
                        result="Success"
                    ))
                    break
                
                # ============================================================
                # SECURITY GATE (IRON GATE LOGIC)
                # ============================================================
                logger.info("SECURITY: Calculating risk...")
                
                # Get element info for risk calculation
                element_info = None
                if action.selector:
                    element_info = await self._get_element_info(self._page, action.selector)
                
                # Calculate risk
                risk, reason = self.security.calculate_risk(
                    action=action_json,
                    target_url=action.value if action.action_type == ActionType.NAVIGATE else current_url,
                    element_info=element_info
                )
                
                logger.info(f"Risk Assessment: {risk}/100 - {reason}")
                
                # ===== IRON GATE LOGIC =====
                
                # Risk >= 90: AUTOMATIC BLOCK
                if risk >= 90:
                    print("\n" + "🚨" * 35)
                    print("🚨 CRITICAL SECURITY ALERT - ACTION BLOCKED 🚨")
                    print("🚨" * 35)
                    print(f"Risk: {risk}/100 (CRITICAL)")
                    print(f"Action: {action.action_type.value}")
                    print(f"Reason: {reason}")
                    print("This action has been automatically BLOCKED for your safety.")
                    print("🚨" * 35 + "\n")
                    
                    logger.warning(f"🚨 ACTION BLOCKED (Risk: {risk}): {reason}")
                    
                    self.history.append(StepRecord(
                        step_num=iteration + 1,
                        action=f"BLOCKED: {action.action_type.value}",
                        result=f"Security Block: {reason}"
                    ))
                    last_error = f"Security blocked this action: {reason}"
                    continue
                
                # Risk >= 40: USER APPROVAL REQUIRED
                elif risk >= 40:
                    approved = self._request_user_approval(action_json, risk, reason)
                    
                    if not approved:
                        logger.info("❌ User denied action")
                        self.history.append(StepRecord(
                            step_num=iteration + 1,
                            action=f"DENIED: {action.action_type.value}",
                            result="User denied"
                        ))
                        last_error = "User denied this action"
                        continue
                    
                    logger.info("✅ User approved action")
                
                # Risk < 40: AUTO-APPROVE
                else:
                    logger.info("✅ Low risk - auto-approved")
                
                # ============================================================
                # VISUAL VERIFICATION (for click actions)
                # ============================================================
                if action.action_type == ActionType.CLICK and element_info:
                    visual_text = element_info.get('text', '')
                    dom_text = element_info.get('text', '')
                    
                    is_safe, verification_reason = self.security.detect_deceptive_ui(
                        visual_text=visual_text,
                        dom_text=dom_text
                    )
                    
                    if not is_safe:
                        logger.warning(f"⚠️ Deceptive UI detected: {verification_reason}")
                        print(f"\n⚠️ VISUAL VERIFICATION FAILED: {verification_reason}")
                        
                        self.history.append(StepRecord(
                            step_num=iteration + 1,
                            action=f"BLOCKED: click {action.selector}",
                            result=f"Visual verification failed: {verification_reason}"
                        ))
                        last_error = f"Deceptive UI detected: {verification_reason}"
                        continue
                
                # ============================================================
                # ACT (execute the action)
                # ============================================================
                logger.info("ACT: Executing action...")
                
                success, message = await self.execute_safe_action(
                    page=self._page,
                    action_plan=action
                )
                
                if success:
                    logger.info(f"✅ {message}")
                    self.history.append(StepRecord(
                        step_num=iteration + 1,
                        action=f"{action.action_type.value} {action.selector or action.value or ''}",
                        result="Success"
                    ))
                    last_error = None
                else:
                    logger.warning(f"❌ {message}")
                    self.history.append(StepRecord(
                        step_num=iteration + 1,
                        action=f"{action.action_type.value} {action.selector or action.value or ''}",
                        result=f"Failed: {message}"
                    ))
                    last_error = message
                
                # Keep last 5 steps
                if len(self.history) > 5:
                    self.history = self.history[-5:]
                
                await self._page.wait_for_timeout(1000)
            
            else:
                logger.warning(f"Max iterations ({self.max_iterations}) reached")
        
        finally:
            logger.info("Stopping browser...")
            await self.stop()


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Example usage with security enabled."""
    agent = AgenticBrowser(
        model="llama3",
        headless=False,
        max_iterations=10,
        enable_security=True  # Security is ON
    )
    
    await agent.run(
        goal="Search for 'Python programming' on Google",
        start_url="https://www.google.com"
    )


if __name__ == "__main__":
    asyncio.run(main())

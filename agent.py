"""
Production-Ready Agentic Browser
================================
A robust browser automation agent with:
- Regex-based JSON extraction (handles conversational LLM output)
- Action history (last 5 steps) to prevent loops
- Action verification (detects NO_EFFECT)
- Comprehensive error recovery
- Security Layer Integration
- SoM-based element targeting

Author: Secure Agentic Browser Project
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

# Import modules
from security import SecurityEngine
from browser_sense import BrowserIntelliSense
from distiller import DOMDistiller

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

# =============================================================================
# SYSTEM PROMPT - Strict JSON Schema
# =============================================================================

SYSTEM_PROMPT = """You are a browser automation agent. You control a web browser to complete tasks.

**CURRENT CONTEXT:**
- URL: {current_url}
- Goal: {user_goal}

**PREVIOUS ACTIONS:**
{history_context}

**AVAILABLE ELEMENTS:**
Use the numbered IDs [1], [2], etc. to refer to elements.
{elements_context}

**OUTPUT FORMAT - STRICT JSON ONLY:**
You MUST respond with valid JSON only. No markdown, no explanation, no text before or after.

{{
    "thought": "Brief reasoning about what to do next",
    "action": "click" | "type" | "navigate" | "scroll" | "wait" | "done",
    "target_id": 12,
    "text": "text to type (for type action)",
    "url": "https://... (for navigate action)"
}}

**ACTION TYPES:**
- click: Click element by target_id
- type: Type text into element (requires target_id and text)
- navigate: Go to URL (requires url)
- scroll: Scroll the page
- wait: Wait 2 seconds
- done: Goal achieved

**CRITICAL RULES:**
1. Output ONLY valid JSON - nothing else
2. Use target_id from the element list [1], [2], etc.
3. If an action failed, try a DIFFERENT approach
4. Do NOT repeat failed actions
5. Use "done" when the goal is achieved
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
class ActionRecord:
    """Record of an action attempt for history."""
    step: int
    action: str
    target: str
    result: str  # "SUCCESS", "FAILED: reason", "NO_EFFECT"
    
    def __str__(self) -> str:
        if "SUCCESS" in self.result:
            return f"Step {self.step}: {self.action} {self.target} → ✓"
        elif "NO_EFFECT" in self.result:
            return f"Step {self.step}: {self.action} {self.target} → (no change)"
        else:
            return f"Step {self.step}: {self.action} {self.target} → ✗ {self.result}"


# =============================================================================
# AGENTIC BROWSER - Production Ready
# =============================================================================

class AgenticBrowser:
    """
    Production-ready browser agent with:
    - Robust JSON extraction
    - Action history
    - Action verification
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        headless: bool = False,
        max_iterations: int = 15,
        enable_security: bool = True
    ):
        """Initialize the agentic browser."""
        self.model = model
        self.headless = headless
        self.max_iterations = max_iterations
        
        # Action history (last 5)
        self.history: List[ActionRecord] = []
        
        # Ollama client
        self.client = AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama"
        )
        
        # Modules
        self.security = SecurityEngine(enabled=enable_security)
        self.som = BrowserIntelliSense()
        self.distiller = DOMDistiller()
        
        # Browser state
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # Tracking
        self._current_step = 0
        self._last_page_hash = ""
        
        logger.info(f"AgenticBrowser initialized (model={model}, security={enable_security})")
    
    # =========================================================================
    # BROWSER LIFECYCLE
    # =========================================================================
    
    async def start(self) -> None:
        """Start the browser."""
        logger.info("Starting browser...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        logger.info("Browser started")
    
    async def stop(self) -> None:
        """Stop the browser."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Browser stop warning: {e}")
        logger.info("Browser stopped")
    
    # =========================================================================
    # ROBUST JSON EXTRACTION (Critical Fix #1)
    # =========================================================================
    
    def _extract_json(self, response_text: str) -> Tuple[Optional[Dict], str]:
        """
        Extract JSON from LLM response using regex.
        
        Handles:
        - Pure JSON responses
        - JSON wrapped in markdown
        - JSON with conversational text before/after
        
        Returns:
            Tuple of (parsed_json, error_message)
        """
        if not response_text:
            return None, "FORMAT_ERROR: Empty response"
        
        # Clean the response
        text = response_text.strip()
        
        # Try 1: Direct JSON parsing
        try:
            return json.loads(text), ""
        except json.JSONDecodeError:
            pass
        
        # Try 2: Remove markdown code blocks
        if "```" in text:
            # Extract content between code blocks
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1)), ""
                except json.JSONDecodeError:
                    pass
        
        # Try 3: Find JSON object with regex
        # Look for { ... } pattern
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                parsed = json.loads(match)
                # Validate it has expected keys
                if 'action' in parsed:
                    logger.debug(f"Extracted JSON via regex: {match[:100]}")
                    return parsed, ""
            except json.JSONDecodeError:
                continue
        
        # Try 4: More aggressive extraction - find first { and last }
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_candidate = text[first_brace:last_brace + 1]
            try:
                parsed = json.loads(json_candidate)
                if 'action' in parsed:
                    return parsed, ""
            except json.JSONDecodeError:
                pass
        
        # All attempts failed
        logger.warning(f"Failed to extract JSON from: {text[:200]}")
        return None, f"FORMAT_ERROR: Could not parse JSON from response"
    
    # =========================================================================
    # ACTION HISTORY (Critical Fix #2)
    # =========================================================================
    
    def _format_history(self) -> str:
        """Format action history for the prompt."""
        if not self.history:
            return "No previous actions."
        
        lines = []
        for record in self.history[-5:]:  # Last 5
            lines.append(str(record))
        
        return "\n".join(lines)
    
    def _add_to_history(
        self,
        action: str,
        target: str,
        result: str
    ) -> None:
        """Add an action to history."""
        self._current_step += 1
        record = ActionRecord(
            step=self._current_step,
            action=action,
            target=target,
            result=result
        )
        self.history.append(record)
        
        # Keep only last 5
        if len(self.history) > 5:
            self.history = self.history[-5:]
    
    # =========================================================================
    # ACTION VERIFICATION (Critical Fix #3)
    # =========================================================================
    
    async def _get_page_state(self) -> Tuple[str, str]:
        """Get current URL and content hash for verification."""
        try:
            url = self._page.url
            content = await self._page.evaluate(
                "() => document.body.innerText.slice(0, 3000)"
            )
            content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            return url, content_hash
        except Exception:
            return "", ""
    
    async def _verify_action_effect(
        self,
        before_url: str,
        before_hash: str
    ) -> bool:
        """Check if the action had any effect on the page."""
        # Wait for potential changes
        await self._page.wait_for_timeout(2000)
        
        after_url, after_hash = await self._get_page_state()
        
        # Check if anything changed
        url_changed = after_url != before_url
        content_changed = after_hash != before_hash
        
        return url_changed or content_changed
    
    # =========================================================================
    # OBSERVE PHASE
    # =========================================================================
    
    async def _observe(self) -> Tuple[str, Dict[int, Any], str]:
        """
        Observe the current page state.
        
        Returns:
            Tuple of (elements_text, element_map, error)
        """
        try:
            # Inject SoM tags
            num_elements, error = await self.som.inject_script(self._page)
            if error:
                logger.warning(f"SoM injection error: {error}")
            
            # Get element map and text
            element_map, elements_text, error = await self.som.get_observation(self._page)
            if error:
                logger.warning(f"Observation error: {error}")
                return "", {}, error
            
            return elements_text, element_map, ""
            
        except Exception as e:
            error = f"OBSERVE_ERROR: {str(e)[:100]}"
            logger.error(error)
            return "", {}, error
    
    # =========================================================================
    # THINK PHASE
    # =========================================================================
    
    async def _think(
        self,
        goal: str,
        elements_text: str,
        last_error: Optional[str] = None
    ) -> Tuple[Optional[Dict], str]:
        """
        Query LLM to get next action.
        
        Returns:
            Tuple of (action_dict, error)
        """
        # Build prompt
        history_context = self._format_history()
        
        # Add last error to history context if present
        if last_error:
            history_context += f"\n⚠️ LAST ACTION FAILED: {last_error}"
        
        prompt = SYSTEM_PROMPT.format(
            current_url=self._page.url,
            user_goal=goal,
            history_context=history_context,
            elements_context=elements_text[:3000] or "No elements found"
        )
        
        # Sanitize for security
        secured_elements = self.security.sanitize_and_wrap(elements_text)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Complete this goal: {goal}"}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"LLM response: {response_text[:200]}")
            
            # Extract JSON
            action_dict, error = self._extract_json(response_text)
            
            if error:
                return None, error
            
            return action_dict, ""
            
        except Exception as e:
            return None, f"LLM_ERROR: {str(e)[:100]}"
    
    # =========================================================================
    # ACT PHASE
    # =========================================================================
    
    async def _act(
        self,
        action_dict: Dict,
        element_map: Dict[int, Any]
    ) -> Tuple[bool, str]:
        """
        Execute an action with verification.
        
        Returns:
            Tuple of (success, result_message)
        """
        action_type = action_dict.get('action', 'unknown')
        target_id = action_dict.get('target_id')
        
        # Capture state before action
        before_url, before_hash = await self._get_page_state()
        
        # Security check
        if action_type in ['navigate']:
            url = action_dict.get('url', '')
            risk, reason = self.security.calculate_risk(action_dict, url)
            
            if risk >= 90:
                return False, f"BLOCKED: {reason} (Risk: {risk})"
            elif risk >= 40:
                logger.warning(f"⚠️ High risk action: {reason}")
        
        # Get element info for type actions (credential check)
        if action_type == 'type' and target_id:
            elem_info = self.som.get_element_info(int(target_id))
            if elem_info:
                risk, reason = self.security.calculate_risk(
                    action_dict, self._page.url, elem_info
                )
                if risk >= 90:
                    return False, f"BLOCKED: {reason} (Risk: {risk})"
        
        # Execute action
        success, message = await self.som.execute_action(
            self._page,
            action_dict,
            element_map
        )
        
        if not success:
            return False, message
        
        # Verify action had effect
        had_effect = await self._verify_action_effect(before_url, before_hash)
        
        if not had_effect and action_type in ['click', 'type']:
            return True, f"{message} (NO_EFFECT: page unchanged)"
        
        return True, message
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    async def run(self, goal: str, start_url: str = "https://www.google.com") -> bool:
        """
        Run the agent to achieve the goal.
        
        Returns:
            bool: True if goal was achieved
        """
        logger.info(f"Starting agent with goal: {goal}")
        
        await self.start()
        
        try:
            # Navigate to start URL
            await self._page.goto(start_url, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(2000)
            
            last_error: Optional[str] = None
            
            for iteration in range(self.max_iterations):
                logger.info(f"\n{'='*60}")
                logger.info(f"ITERATION {iteration + 1}/{self.max_iterations}")
                logger.info(f"{'='*60}")
                
                # ============================================================
                # OBSERVE
                # ============================================================
                logger.info("📷 OBSERVE")
                elements_text, element_map, obs_error = await self._observe()
                
                if obs_error:
                    logger.warning(f"Observation error: {obs_error}")
                    last_error = obs_error
                    continue
                
                logger.info(f"   Found {len(element_map)} interactive elements")
                
                # ============================================================
                # THINK
                # ============================================================
                logger.info("🧠 THINK")
                action_dict, think_error = await self._think(
                    goal=goal,
                    elements_text=elements_text,
                    last_error=last_error
                )
                
                if think_error:
                    logger.warning(f"Think error: {think_error}")
                    self._add_to_history("think", "", f"FAILED: {think_error}")
                    last_error = think_error
                    continue
                
                thought = action_dict.get('thought', '')
                action_type = action_dict.get('action', 'unknown')
                target_id = action_dict.get('target_id', '')
                
                logger.info(f"   Thought: {thought[:80]}")
                logger.info(f"   Action: {action_type} (target: {target_id})")
                
                # Check if done
                if action_type == 'done':
                    logger.info("✅ GOAL ACHIEVED!")
                    self._add_to_history("done", "", "SUCCESS")
                    return True
                
                # ============================================================
                # ACT
                # ============================================================
                logger.info("⚡ ACT")
                success, result = await self._act(action_dict, element_map)
                
                target_str = f"#{target_id}" if target_id else ""
                
                if success:
                    logger.info(f"   ✓ {result}")
                    
                    if "NO_EFFECT" in result:
                        self._add_to_history(action_type, target_str, "NO_EFFECT")
                        last_error = "Action had no effect on the page"
                    else:
                        self._add_to_history(action_type, target_str, "SUCCESS")
                        last_error = None
                else:
                    logger.warning(f"   ✗ {result}")
                    self._add_to_history(action_type, target_str, f"FAILED: {result}")
                    last_error = result
                
                # Cleanup overlays
                await self.som.cleanup(self._page)
                
                # Brief pause
                await self._page.wait_for_timeout(500)
            
            logger.warning(f"Max iterations ({self.max_iterations}) reached")
            return False
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return False
        finally:
            await self.stop()


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Example usage."""
    agent = AgenticBrowser(
        model="llama3",
        headless=False,
        max_iterations=15,
        enable_security=True
    )
    
    success = await agent.run(
        goal="Search for 'Python programming' on Wikipedia",
        start_url="https://en.wikipedia.org"
    )
    
    print(f"\n{'='*60}")
    print(f"Agent finished: {'SUCCESS' if success else 'INCOMPLETE'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

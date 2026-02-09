# Agentic browser using Ollama + Playwright
# Observe -> Think -> Act -> Verify loop

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

# Import modules
from security import SecurityEngine
from browser_sense import BrowserIntelliSense
from distiller import DOMDistiller

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")


# System prompt for the LLM
SYSTEM_PROMPT = """You are a precise browser automation agent.

GOAL: {goal}
CURRENT URL: {url}
HISTORY: {history}

PAGE ELEMENTS:
{dom_tree}

RULES:
1. You must output VALID JSON only. No conversation, no explanation.
2. If you are stuck, use the 'scroll_down' action to see more elements.
3. If you see a popup or cookie banner, close it first.
4. Do NOT repeat actions that already failed.
5. Use the exact element IDs from the PAGE ELEMENTS list.
6. IMPORTANT: If you 'type' into a search box, you usually need to 'press_enter' on the same target_id to submit.
7. If the URL doesn't change after an action, try a different action (like 'press_enter' or clicking a button).

RESPONSE FORMAT (JSON ONLY):
{{
  "thought": "Brief reasoning of what to do next",
  "action": "click" | "type" | "press_enter" | "scroll_down" | "scroll_up" | "wait" | "done",
  "target_id": 12,
  "value": "search query"
}}

ACTION TYPES:
- click: Click element by target_id
- type: Type text into element (requires target_id and value)
- press_enter: Press Enter key on element (use after type to submit)
- scroll_down: Scroll page down to see more
- scroll_up: Scroll page up
- wait: Wait for page to load
- done: Goal is achieved

CRITICAL: Output ONLY the JSON object. No other text."""


@dataclass
class StepRecord:
    step: int
    action: str
    target: str
    result: str
    
    def to_dict(self) -> Dict:
        return {
            "step": self.step,
            "action": f"{self.action} {self.target}".strip(),
            "result": self.result
        }
    
    def __str__(self) -> str:
        return f"Step {self.step}: {self.action} {self.target} → {self.result}"


class OllamaAgent:
    
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        headless: bool = False,
        max_iterations: int = 20,
        enable_security: bool = True,
        debug_mode: bool = False
    ):
        self.model = model
        self.headless = headless
        self.max_iterations = max_iterations
        self.debug_mode = debug_mode
        
        self.history: List[StepRecord] = []  # action history for avoiding loops
        
        self.client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
        
        self.security = SecurityEngine(enabled=enable_security)
        self.som = BrowserIntelliSense(debug_mode=debug_mode)
        self.distiller = DOMDistiller()
        
        # Browser state
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # Step counter
        self._step = 0
        
        logger.info(f"OllamaAgent initialized (model={model}, debug={debug_mode})")
    
    # BROWSER LIFECYCLE
    
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
            logger.warning(f"Stop warning: {e}")
        logger.info("Browser stopped")
    
    # JSON EXTRACTION (Robust)
    
    def extract_json_from_text(self, response_text: str) -> Tuple[Optional[Dict], str]:
        """
        Extract JSON from LLM response using multiple strategies.
        
        Handles:
        - Pure JSON
        - JSON in markdown code blocks
        - JSON with conversational text before/after
        
        Returns:
            Tuple of (parsed_json, error_message)
        """
        if not response_text:
            return None, "FORMAT_ERROR: Empty response"
        
        text = response_text.strip()
        
        # Strategy 1: Direct parse
        try:
            return json.loads(text), ""
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract from markdown
        if "```" in text:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1)), ""
                except json.JSONDecodeError:
                    pass
        
        # try regex for nested json
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                parsed = json.loads(match)
                if 'action' in parsed:
                    return parsed, ""
            except json.JSONDecodeError:
                continue
        
        # Strategy 4: First { to last }
        first = text.find('{')
        last = text.rfind('}')
        
        if first != -1 and last > first:
            try:
                parsed = json.loads(text[first:last + 1])
                if 'action' in parsed:
                    return parsed, ""
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"Failed to extract JSON: {text[:100]}")
        return None, "FORMAT_ERROR: Could not parse JSON"
    
    # STATE MEMORY
    
    def _format_history(self) -> str:
        """Format history for the system prompt."""
        if not self.history:
            return "No previous actions."
        
        lines = []
        for record in self.history[-5:]:  # Last 5
            lines.append(str(record))
        
        return "\n".join(lines)
    
    def _add_to_history(self, action: str, target: str, result: str) -> None:
        self._step += 1
        record = StepRecord(
            step=self._step,
            action=action,
            target=target,
            result=result
        )
        self.history.append(record)
        
        # Keep last 5
        if len(self.history) > 5:
            self.history = self.history[-5:]
    
    # OBSERVE PHASE
    
    async def observe(self) -> Tuple[str, Dict[int, Any], str]:
        """
        Observe the current page state.
        
        Returns:
            Tuple of (elements_text, element_map, error)
        """
        logger.info("📷 OBSERVE")
        
        try:
            # Inject SoM
            num_elements, error = await self.som.inject_script(self._page)
            if error:
                logger.warning(f"SoM error: {error}")
            
            # Get observation
            element_map, elements_text, error = await self.som.get_observation(self._page)
            
            if error:
                return "", {}, error
            
            logger.info(f"   Found {len(element_map)} elements")
            return elements_text, element_map, ""
            
        except Exception as e:
            return "", {}, f"OBSERVE_ERROR: {str(e)[:100]}"
    
    # THINK PHASE
    
    async def think(
        self,
        goal: str,
        elements_text: str,
        last_error: Optional[str] = None
    ) -> Tuple[Optional[Dict], str]:
        """
        Query LLM for next action.
        
        Returns:
            Tuple of (action_dict, error)
        """
        logger.info("🧠 THINK")
        
        # Build history with last error
        history_context = self._format_history()
        if last_error:
            history_context += f"\n⚠️ LAST ERROR: {last_error}"
        
        # Build prompt
        prompt = SYSTEM_PROMPT.format(
            goal=goal,
            url=self._page.url,
            history=history_context,
            dom_tree=elements_text[:4000] or "No elements found"
        )
        
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
            logger.debug(f"LLM response: {response_text[:150]}")
            
            # Extract JSON
            action_dict, error = self.extract_json_from_text(response_text)
            
            if action_dict:
                thought = action_dict.get('thought', '')[:60]
                logger.info(f"   Thought: {thought}")
            
            return action_dict, error
            
        except Exception as e:
            return None, f"LLM_ERROR: {str(e)[:100]}"
    
    # ACT PHASE
    
    async def act(
        self,
        action_dict: Dict,
        element_map: Dict[int, Any]
    ) -> Tuple[bool, str]:
        """
        Execute the action.
        
        Returns:
            Tuple of (success, result_message)
        """
        logger.info("⚡ ACT")
        
        action_type = action_dict.get('action', 'unknown')
        target_id = action_dict.get('target_id')
        value = action_dict.get('value', '')
        
        logger.info(f"   Action: {action_type}, Target: {target_id}, Value: {value[:20] if value else ''}")
        
        # Security check for navigation
        if action_type == 'navigate':
            url = action_dict.get('url') or value
            risk, reason = self.security.calculate_risk(
                {'action': 'navigate', 'value': url}, url
            )
            if risk >= 90:
                return False, f"BLOCKED: {reason}"
        
        # Check for repeated type actions (stubborn model fix)
        if action_type == 'type':
            last_step = self.history[-1] if self.history else None
            if (last_step and 
                last_step.action == 'type' and 
                last_step.target == f"#{target_id}"): # target is formatted as '#ID'
                
                logger.warning(f"Repeated type action on #{target_id}. Forcing press_enter.")
                action_type = 'press_enter'
                # Keep the target_id
                action_dict['action'] = 'press_enter' # Update action_dict for execute_action
                # No need to change target_id, press_enter can use it
        
        # Execute via SoM
        success, message = await self.som.execute_action(
            self._page,
            action_dict,
            element_map,
            debug=self.debug_mode
        )
        
        return success, message
    
    # VERIFY PHASE
    
    async def verify(
        self,
        before_url: str,
        before_hash: str
    ) -> Tuple[bool, str]:
        """
        Verify if the action had an effect.
        
        Returns:
            Tuple of (page_changed, verification_message)
        """
        logger.info("🔍 VERIFY")
        
        # Wait for page to settle
        await self._page.wait_for_load_state('domcontentloaded')
        
        after_url = self._page.url
        after_hash = await self.som.get_page_hash(self._page)
        
        url_changed = after_url != before_url
        content_changed = after_hash != before_hash
        
        if url_changed:
            logger.info(f"   ✓ URL changed: {before_url} → {after_url}")
            return True, f"URL changed to {after_url}"
        elif content_changed:
            logger.info("   ✓ Page content changed")
            return True, "Page content updated"
        else:
            logger.info("   ⚠ No visible change detected")
            return False, "NO_EFFECT"
    
    # MAIN LOOP: Observe → Think → Act → Verify
    
    async def run(self, goal: str, start_url: str = "https://www.google.com") -> bool:
        """
        Run the agent to achieve the goal.
        
        Args:
            goal: Natural language goal
            start_url: Starting URL
            
        Returns:
            True if goal achieved
        """
        logger.info(f"{'='*60}")
        logger.info(f"STARTING AGENT")
        logger.info(f"Goal: {goal}")
        logger.info(f"{'='*60}")
        
        await self.start()
        
        try:
            # Navigate to start
            logger.info(f"Navigating to {start_url}")
            await self._page.goto(start_url, wait_until="domcontentloaded")
            try:
                await self._page.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                logger.warning("Initial navigation wait timed out (proceeding anyway)")
            
            last_error: Optional[str] = None
            
            for iteration in range(self.max_iterations):
                logger.info(f"\n{'─'*40}")
                logger.info(f"ITERATION {iteration + 1}/{self.max_iterations}")
                logger.info(f"{'─'*40}")
                
                # Capture state before
                before_url = self._page.url
                before_hash = await self.som.get_page_hash(self._page)
                
                elements_text, element_map, obs_error = await self.observe()
                
                if obs_error:
                    last_error = obs_error
                    continue
                
                action_dict, think_error = await self.think(
                    goal=goal,
                    elements_text=elements_text,
                    last_error=last_error
                )
                
                if think_error:
                    self._add_to_history("think", "", f"FAILED: {think_error}")
                    last_error = think_error
                    continue
                
                action_type = action_dict.get('action', 'unknown')
                target_id = action_dict.get('target_id', '')
                
                # Check for done
                if action_type == 'done':
                    logger.info("\n✅ GOAL ACHIEVED!")
                    self._add_to_history("done", "", "Goal complete")
                    return True
                
                success, result = await self.act(action_dict, element_map)
                
                target_str = f"#{target_id}" if target_id else ""
                
                if not success:
                    self._add_to_history(action_type, target_str, f"FAILED: {result}")
                    last_error = result
                    logger.warning(f"   ✗ {result}")
                    continue
                
                page_changed, verify_msg = await self.verify(before_url, before_hash)
                
                if page_changed:
                    self._add_to_history(action_type, target_str, verify_msg)
                    last_error = None
                else:
                    self._add_to_history(action_type, target_str, "NO_EFFECT")
                    last_error = "Action had no visible effect"
                
                # Cleanup overlays
                await self.som.cleanup(self._page)
            
            logger.warning(f"\n⚠ Max iterations ({self.max_iterations}) reached")
            return False
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.stop()


# CONVENIENCE ALIAS

# Alias for backward compatibility
AgenticBrowser = OllamaAgent


# CLI ENTRY

async def main():
    """CLI entry point."""
    import sys
    
    # Default goal
    goal = "Search for 'Python programming' on Wikipedia"
    start_url = "https://en.wikipedia.org"
    
    # Parse args
    if len(sys.argv) > 1:
        goal = sys.argv[1]
    if len(sys.argv) > 2:
        start_url = sys.argv[2]
    
    agent = OllamaAgent(
        model=OLLAMA_MODEL,
        headless=False,
        max_iterations=15,
        debug_mode=True
    )
    
    success = await agent.run(goal=goal, start_url=start_url)
    
    print(f"\n{'='*60}")
    print(f"Result: {'✅ SUCCESS' if success else '❌ INCOMPLETE'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())

"""
BrowserIntelliSense - Set-of-Mark (SoM) Implementation
======================================================
Robust implementation with:
- Safe Playwright execution (no crashes)
- Error strings returned instead of exceptions
- Timeout handling

Author: Secure Agentic Browser Project
"""

import hashlib
import logging
from typing import Dict, List, Tuple, Optional
from playwright.async_api import Page, Locator
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


# JavaScript code to inject into the page for element tagging
TAGGING_SCRIPT = """
(function() {
    // Remove any existing tags
    const existingTags = document.querySelectorAll('[data-agent-tag="true"]');
    existingTags.forEach(tag => tag.remove());
    
    const existingMarked = document.querySelectorAll('[data-agent-id]');
    existingMarked.forEach(elem => elem.removeAttribute('data-agent-id'));
    
    // Find all interactive elements
    const selectors = [
        'a[href]',
        'button',
        'input',
        'textarea',
        'select',
        '[onclick]',
        '[role="button"]',
        '[role="link"]',
        '[role="textbox"]',
        '[tabindex]:not([tabindex="-1"])'
    ];
    
    const allElements = document.querySelectorAll(selectors.join(','));
    
    // Filter visible elements and assign IDs
    const elements = [];
    let idCounter = 1;
    
    allElements.forEach(elem => {
        // Check if element is visible
        const style = window.getComputedStyle(elem);
        const rect = elem.getBoundingClientRect();
        
        const isVisible = (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0' &&
            rect.width > 0 &&
            rect.height > 0 &&
            rect.top < window.innerHeight &&
            rect.bottom > 0 &&
            rect.left < window.innerWidth &&
            rect.right > 0
        );
        
        if (isVisible) {
            elem.setAttribute('data-agent-id', idCounter);
            elements.push({
                id: idCounter,
                element: elem
            });
            idCounter++;
        }
    });
    
    // Create visual overlays
    elements.forEach(item => {
        const elem = item.element;
        const id = item.id;
        const rect = elem.getBoundingClientRect();
        
        // Create overlay container
        const overlay = document.createElement('div');
        overlay.setAttribute('data-agent-tag', 'true');
        overlay.style.position = 'fixed';
        overlay.style.left = rect.left + 'px';
        overlay.style.top = rect.top + 'px';
        overlay.style.width = '24px';
        overlay.style.height = '20px';
        overlay.style.backgroundColor = '#FF0000';
        overlay.style.color = '#FFFFFF';
        overlay.style.border = '1px solid #FFFFFF';
        overlay.style.borderRadius = '3px';
        overlay.style.fontSize = '12px';
        overlay.style.fontWeight = 'bold';
        overlay.style.fontFamily = 'Arial, sans-serif';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '999999';
        overlay.style.pointerEvents = 'none';
        overlay.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
        overlay.textContent = id.toString();
        
        document.body.appendChild(overlay);
    });
    
    return elements.length;
})();
"""


class BrowserIntelliSense:
    """
    Implements the Set-of-Mark (SoM) approach for web interaction.
    
    Features:
    - Robust error handling (returns error strings, doesn't crash)
    - Page content hashing for change detection
    - Safe Playwright execution
    """
    
    def __init__(self):
        self.element_map: Dict[int, Locator] = {}
        self.element_info: List[Dict] = []
        self._last_content_hash: Optional[str] = None
        logger.info("BrowserIntelliSense initialized")
    
    async def inject_script(self, page: Page) -> Tuple[int, str]:
        """
        Inject the tagging script into the page.
        
        Returns:
            Tuple of (num_elements, error_message)
            If successful, error_message is empty string.
        """
        logger.info("Injecting Set-of-Mark script...")
        
        try:
            num_elements = await page.evaluate(TAGGING_SCRIPT)
            await page.wait_for_timeout(100)
            logger.info(f"Tagged {num_elements} interactive elements")
            return num_elements, ""
            
        except PlaywrightTimeoutError:
            error = "TIMEOUT: Script injection timed out"
            logger.error(error)
            return 0, error
        except Exception as e:
            error = f"SCRIPT_ERROR: {str(e)[:100]}"
            logger.error(error)
            return 0, error
    
    async def get_observation(self, page: Page) -> Tuple[Dict[int, Locator], str, str]:
        """
        Get the observation data from the page.
        
        Returns:
            Tuple containing:
            - element_map: Dict mapping ID -> Playwright Locator
            - element_text: Clean text listing of elements
            - error: Error message (empty if successful)
        """
        logger.info("Extracting observation data...")
        
        # Clear previous mappings
        self.element_map = {}
        self.element_info = []
        
        try:
            # Get all tagged elements
            tagged_elements = await page.query_selector_all('[data-agent-id]')
            
            element_lines = []
            
            for elem in tagged_elements:
                try:
                    # Get the ID
                    elem_id = await elem.get_attribute('data-agent-id')
                    if not elem_id:
                        continue
                    
                    elem_id = int(elem_id)
                    
                    # Get element info
                    tag_name = await elem.evaluate('el => el.tagName.toLowerCase()')
                    text_content = await elem.evaluate(
                        'el => (el.innerText || el.value || el.placeholder || "").trim()'
                    )
                    elem_type = await elem.get_attribute('type') or tag_name
                    href = await elem.get_attribute('href') or ''
                    
                    # Truncate long text
                    if len(text_content) > 50:
                        text_content = text_content[:47] + "..."
                    
                    # Store locator
                    self.element_map[elem_id] = page.locator(f'[data-agent-id="{elem_id}"]')
                    
                    # Store info
                    info = {
                        'id': elem_id,
                        'type': elem_type,
                        'tag': tag_name,
                        'text': text_content,
                        'href': href
                    }
                    self.element_info.append(info)
                    
                    # Create text line
                    if text_content:
                        line = f"[{elem_id}] {elem_type}: \"{text_content}\""
                    else:
                        line = f"[{elem_id}] {elem_type}"
                    
                    element_lines.append(line)
                    
                except Exception as e:
                    logger.warning(f"Failed to extract element: {e}")
                    continue
            
            element_text = "\n".join(element_lines)
            logger.info(f"Extracted {len(self.element_map)} elements")
            
            return self.element_map, element_text, ""
            
        except Exception as e:
            error = f"OBSERVATION_ERROR: {str(e)[:100]}"
            logger.error(error)
            return {}, "", error
    
    async def execute_action(
        self,
        page: Page,
        action_dict: Dict,
        element_map: Dict[int, Locator]
    ) -> Tuple[bool, str]:
        """
        Execute an action with robust error handling.
        
        Returns:
            Tuple of (success: bool, result_message: str)
            If failed, result_message contains the specific error.
        """
        action_type = action_dict.get('action', '').lower()
        element_id = action_dict.get('target_id') or action_dict.get('id')
        
        # Handle navigation separately (no element needed)
        if action_type == 'navigate':
            url = action_dict.get('url') or action_dict.get('value', '')
            if not url:
                return False, "ERROR: Navigate requires URL"
            return await self._safe_navigate(page, url)
        
        if action_type == 'scroll':
            amount = action_dict.get('amount') or action_dict.get('value', 500)
            return await self._safe_scroll(page, int(amount))
        
        if action_type == 'wait':
            seconds = action_dict.get('seconds') or action_dict.get('value', 2)
            await page.wait_for_timeout(int(seconds) * 1000)
            return True, f"Waited {seconds} seconds"
        
        if action_type == 'done':
            return True, "GOAL_COMPLETE"
        
        # For click/type, we need element_id
        if element_id is None:
            return False, "ERROR: No target_id provided for action"
        
        # Convert to int if string
        if isinstance(element_id, str):
            try:
                element_id = int(element_id)
            except ValueError:
                return False, f"ERROR: Invalid target_id '{element_id}'"
        
        # Get locator
        if element_id not in element_map:
            return False, f"ERROR: Element #{element_id} not found (may have disappeared)"
        
        locator = element_map[element_id]
        
        # Execute action with robust error handling
        if action_type == 'click':
            return await self._safe_click(page, locator, element_id)
        
        elif action_type == 'type':
            text = action_dict.get('text') or action_dict.get('value', '')
            if not text:
                return False, "ERROR: Type requires text value"
            return await self._safe_type(page, locator, element_id, text)
        
        elif action_type == 'press_enter':
            return await self._safe_press_enter(page, locator, element_id)
        
        else:
            return False, f"ERROR: Unknown action type '{action_type}'"
    
    async def _safe_click(
        self, page: Page, locator: Locator, elem_id: int
    ) -> Tuple[bool, str]:
        """Click with comprehensive error handling."""
        try:
            logger.info(f"Clicking element #{elem_id}")
            await locator.click(timeout=5000)
            await page.wait_for_timeout(500)
            return True, f"Clicked element #{elem_id}"
            
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: Element #{elem_id} took too long to become clickable"
        
        except Exception as e:
            error_str = str(e).lower()
            
            # Parse specific Playwright errors
            if "element is obscured" in error_str or "intercept" in error_str:
                return False, f"OBSCURED: Element #{elem_id} is hidden behind another element"
            elif "element is not visible" in error_str:
                return False, f"INVISIBLE: Element #{elem_id} is not visible on screen"
            elif "element is detached" in error_str or "target closed" in error_str:
                return False, f"DETACHED: Element #{elem_id} was removed from the page"
            elif "element is outside" in error_str:
                return False, f"OFFSCREEN: Element #{elem_id} is outside the viewport"
            else:
                return False, f"CLICK_ERROR: {str(e)[:80]}"
    
    async def _safe_type(
        self, page: Page, locator: Locator, elem_id: int, text: str
    ) -> Tuple[bool, str]:
        """Type with comprehensive error handling."""
        try:
            logger.info(f"Typing into element #{elem_id}")
            await locator.fill(text, timeout=5000)
            await page.wait_for_timeout(300)
            return True, f"Typed '{text[:30]}...' into element #{elem_id}"
            
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: Element #{elem_id} not ready for input"
        
        except Exception as e:
            error_str = str(e).lower()
            
            if "not an input" in error_str or "cannot be edited" in error_str:
                return False, f"NOT_EDITABLE: Element #{elem_id} is not a text input"
            elif "element is detached" in error_str:
                return False, f"DETACHED: Element #{elem_id} was removed from the page"
            else:
                return False, f"TYPE_ERROR: {str(e)[:80]}"
    
    async def _safe_press_enter(
        self, page: Page, locator: Locator, elem_id: int
    ) -> Tuple[bool, str]:
        """Press enter with comprehensive error handling."""
        try:
            logger.info(f"Pressing Enter on element #{elem_id}")
            await locator.press('Enter', timeout=5000)
            await page.wait_for_timeout(1000)
            return True, f"Pressed Enter on element #{elem_id}"
            
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: Element #{elem_id} not responding"
        except Exception as e:
            return False, f"KEYPRESS_ERROR: {str(e)[:80]}"
    
    async def _safe_navigate(self, page: Page, url: str) -> Tuple[bool, str]:
        """Navigate with comprehensive error handling."""
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1000)
            return True, f"Navigated to {url}"
            
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: Page {url} took too long to load"
        except Exception as e:
            return False, f"NAVIGATION_ERROR: {str(e)[:80]}"
    
    async def _safe_scroll(self, page: Page, amount: int) -> Tuple[bool, str]:
        """Scroll with error handling."""
        try:
            await page.evaluate(f"window.scrollBy(0, {amount})")
            await page.wait_for_timeout(500)
            return True, f"Scrolled {amount}px"
        except Exception as e:
            return False, f"SCROLL_ERROR: {str(e)[:80]}"
    
    async def get_page_hash(self, page: Page) -> str:
        """Get a hash of the current page content for change detection."""
        try:
            content = await page.evaluate("() => document.body.innerText.slice(0, 5000)")
            url = page.url
            hash_input = f"{url}:{content}"
            return hashlib.md5(hash_input.encode()).hexdigest()[:16]
        except Exception:
            return ""
    
    def get_element_text_list(self) -> str:
        """Get a formatted text list of all elements."""
        lines = []
        for info in self.element_info:
            if info['text']:
                line = f"[{info['id']}] {info['type']}: \"{info['text']}\""
            else:
                line = f"[{info['id']}] {info['type']}"
            lines.append(line)
        return "\n".join(lines)
    
    def get_element_info(self, elem_id: int) -> Optional[Dict]:
        """Get element info by ID."""
        for info in self.element_info:
            if info['id'] == elem_id:
                return info
        return None
    
    async def cleanup(self, page: Page) -> None:
        """Remove all visual overlays from the page."""
        try:
            await page.evaluate("""
                () => {
                    const tags = document.querySelectorAll('[data-agent-tag="true"]');
                    tags.forEach(tag => tag.remove());
                    
                    const marked = document.querySelectorAll('[data-agent-id]');
                    marked.forEach(elem => elem.removeAttribute('data-agent-id'));
                }
            """)
            logger.info("Cleaned up visual overlays")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")

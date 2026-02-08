"""
BrowserIntelliSense - Production-Grade SoM Implementation
=========================================================
Robust implementation with:
- Overlap detection (skip covered elements)
- Debug highlighting (red box before click)
- Smart waits (networkidle instead of static timeouts)
- Safe Playwright execution (no crashes)

Author: Secure Agentic Browser Project
"""

import hashlib
import logging
from typing import Dict, List, Tuple, Optional
from playwright.async_api import Page, Locator
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


# JavaScript for SoM tagging with OVERLAP DETECTION
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
        'button:not([disabled])',
        'input:not([type="hidden"]):not([disabled])',
        'textarea:not([disabled])',
        'select:not([disabled])',
        '[onclick]',
        '[role="button"]',
        '[role="link"]',
        '[role="textbox"]',
        '[role="searchbox"]',
        '[tabindex]:not([tabindex="-1"])'
    ];
    
    const allElements = document.querySelectorAll(selectors.join(','));
    
    // Helper: Check if element is covered by another element (overlap detection)
    function isElementCovered(elem) {
        const rect = elem.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // Get element at center point
        const topElement = document.elementFromPoint(centerX, centerY);
        
        if (!topElement) return true;  // Off-screen
        
        // Check if the element at point is the target or a descendant
        return !elem.contains(topElement) && !topElement.contains(elem) && topElement !== elem;
    }
    
    // Filter visible, non-covered elements and assign IDs
    const elements = [];
    let idCounter = 1;
    
    allElements.forEach(elem => {
        const style = window.getComputedStyle(elem);
        const rect = elem.getBoundingClientRect();
        
        // Visibility checks
        const isVisible = (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0' &&
            rect.width > 5 &&
            rect.height > 5 &&
            rect.top < window.innerHeight &&
            rect.bottom > 0 &&
            rect.left < window.innerWidth &&
            rect.right > 0
        );
        
        if (!isVisible) return;
        
        // OVERLAP DETECTION: Skip if covered by popup/modal
        if (isElementCovered(elem)) {
            console.log('Skipping covered element:', elem);
            return;
        }
        
        elem.setAttribute('data-agent-id', idCounter);
        elements.push({
            id: idCounter,
            element: elem
        });
        idCounter++;
    });
    
    // Create visual overlays
    elements.forEach(item => {
        const elem = item.element;
        const id = item.id;
        const rect = elem.getBoundingClientRect();
        
        const overlay = document.createElement('div');
        overlay.setAttribute('data-agent-tag', 'true');
        overlay.style.cssText = `
            position: fixed;
            left: ${rect.left}px;
            top: ${rect.top}px;
            width: 22px;
            height: 18px;
            background-color: #FF0000;
            color: #FFFFFF;
            border: 1px solid #FFFFFF;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            font-family: Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 999999;
            pointer-events: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        `;
        overlay.textContent = id.toString();
        
        document.body.appendChild(overlay);
    });
    
    return elements.length;
})();
"""


# JavaScript for highlighting element before action
HIGHLIGHT_SCRIPT = """
(selector) => {
    // Remove existing highlights
    const existing = document.querySelectorAll('[data-agent-highlight="true"]');
    existing.forEach(h => h.remove());
    
    const elem = document.querySelector(selector);
    if (!elem) return false;
    
    const rect = elem.getBoundingClientRect();
    
    // Create red box highlight
    const highlight = document.createElement('div');
    highlight.setAttribute('data-agent-highlight', 'true');
    highlight.style.cssText = `
        position: fixed;
        left: ${rect.left - 3}px;
        top: ${rect.top - 3}px;
        width: ${rect.width + 6}px;
        height: ${rect.height + 6}px;
        border: 3px solid #FF0000;
        border-radius: 4px;
        background: rgba(255, 0, 0, 0.1);
        z-index: 999998;
        pointer-events: none;
        animation: pulse 0.5s ease-in-out 2;
    `;
    
    // Add animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(highlight);
    
    // Auto-remove after 2 seconds
    setTimeout(() => highlight.remove(), 2000);
    
    return true;
}
"""


class BrowserIntelliSense:
    """
    Production-grade Set-of-Mark (SoM) implementation.
    
    Features:
    - Overlap detection (skips covered elements)
    - Debug highlighting (red box before actions)
    - Smart waits (networkidle)
    - Robust error handling
    """
    
    def __init__(self, debug_mode: bool = False):
        self.element_map: Dict[int, Locator] = {}
        self.element_info: List[Dict] = []
        self.debug_mode = debug_mode
        self._last_content_hash: Optional[str] = None
        logger.info(f"BrowserIntelliSense initialized (debug={debug_mode})")
    
    async def inject_script(self, page: Page) -> Tuple[int, str]:
        """
        Inject SoM tagging script with overlap detection.
        
        Returns:
            Tuple of (num_elements, error_message)
        """
        logger.info("Injecting Set-of-Mark script...")
        
        try:
            # Wait for page to be stable
            await page.wait_for_load_state('domcontentloaded')
            
            num_elements = await page.evaluate(TAGGING_SCRIPT)
            logger.info(f"Tagged {num_elements} interactive elements (overlap-filtered)")
            return num_elements, ""
            
        except PlaywrightTimeoutError:
            return 0, "TIMEOUT: Script injection timed out"
        except Exception as e:
            return 0, f"SCRIPT_ERROR: {str(e)[:100]}"
    
    async def get_observation(self, page: Page) -> Tuple[Dict[int, Locator], str, str]:
        """
        Get observation data from tagged elements.
        
        Returns:
            Tuple of (element_map, element_text, error)
        """
        logger.info("Extracting observation data...")
        
        self.element_map = {}
        self.element_info = []
        
        try:
            tagged_elements = await page.query_selector_all('[data-agent-id]')
            element_lines = []
            
            for elem in tagged_elements:
                try:
                    elem_id = await elem.get_attribute('data-agent-id')
                    if not elem_id:
                        continue
                    
                    elem_id = int(elem_id)
                    
                    # Get element info
                    info = await page.evaluate("""(el) => {
                        return {
                            tag: el.tagName.toLowerCase(),
                            type: el.getAttribute('type') || el.tagName.toLowerCase(),
                            text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 50),
                            href: el.getAttribute('href') || '',
                            name: el.getAttribute('name') || '',
                            id: el.id || ''
                        };
                    }""", elem)
                    
                    # Store locator
                    self.element_map[elem_id] = page.locator(f'[data-agent-id="{elem_id}"]')
                    
                    # Store info
                    info['elem_id'] = elem_id
                    self.element_info.append(info)
                    
                    # Create text line
                    text_part = f': "{info["text"]}"' if info['text'] else ''
                    element_lines.append(f"[{elem_id}] {info['type']}{text_part}")
                    
                except Exception as e:
                    logger.warning(f"Failed to extract element: {e}")
                    continue
            
            element_text = "\n".join(element_lines)
            logger.info(f"Extracted {len(self.element_map)} elements")
            
            return self.element_map, element_text, ""
            
        except Exception as e:
            return {}, "", f"OBSERVATION_ERROR: {str(e)[:100]}"
    
    async def highlight_element(self, page: Page, elem_id: int) -> bool:
        """
        Draw red box around element before clicking (debug mode).
        
        Args:
            page: Playwright Page
            elem_id: Element ID to highlight
            
        Returns:
            True if highlighted successfully
        """
        try:
            selector = f'[data-agent-id="{elem_id}"]'
            result = await page.evaluate(HIGHLIGHT_SCRIPT, selector)
            if result:
                logger.info(f"🔴 Highlighted element #{elem_id}")
                # Brief pause to show highlight
                await page.wait_for_timeout(300)
            return result
        except Exception as e:
            logger.warning(f"Highlight failed: {e}")
            return False
    
    async def execute_action(
        self,
        page: Page,
        action_dict: Dict,
        element_map: Dict[int, Locator],
        debug: bool = False
    ) -> Tuple[bool, str]:
        """
        Execute action with robust error handling.
        
        Args:
            page: Playwright Page
            action_dict: Action with 'action', 'target_id', 'value' keys
            element_map: ID -> Locator mapping
            debug: If True, highlight element before action
            
        Returns:
            Tuple of (success, result_message)
        """
        action_type = action_dict.get('action', '').lower()
        target_id = action_dict.get('target_id') or action_dict.get('id')
        
        # Handle non-element actions
        if action_type == 'navigate':
            url = action_dict.get('url') or action_dict.get('value', '')
            return await self._safe_navigate(page, url)
        
        if action_type in ['scroll', 'scroll_down']:
            return await self._safe_scroll(page, 500)
        
        if action_type == 'scroll_up':
            return await self._safe_scroll(page, -500)
        
        if action_type == 'wait':
            return await self._smart_wait(page)
        
        if action_type == 'done':
            return True, "GOAL_COMPLETE"
        
        # For element actions, need target_id
        if target_id is None:
            return False, "ERROR: No target_id provided"
        
        # Convert to int
        try:
            target_id = int(target_id)
        except (ValueError, TypeError):
            return False, f"ERROR: Invalid target_id '{target_id}'"
        
        # Get locator
        if target_id not in element_map:
            return False, f"ERROR: Element #{target_id} not found"
        
        locator = element_map[target_id]
        
        # Debug highlight
        if debug or self.debug_mode:
            await self.highlight_element(page, target_id)
        
        # Execute
        if action_type == 'click':
            return await self._safe_click(page, locator, target_id)
        elif action_type == 'type':
            text = action_dict.get('text') or action_dict.get('value', '')
            return await self._safe_type(page, locator, target_id, text)
        elif action_type == 'press_enter':
            return await self._safe_press_enter(page, locator, target_id)
        else:
            return False, f"ERROR: Unknown action '{action_type}'"
    
    async def _safe_click(
        self, page: Page, locator: Locator, elem_id: int
    ) -> Tuple[bool, str]:
        """Click with comprehensive error handling."""
        try:
            logger.info(f"Clicking element #{elem_id}")
            await locator.click(timeout=5000)
            
            # Smart wait for page response
            await self._smart_wait(page)
            
            return True, f"Clicked #{elem_id}"
            
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: #{elem_id} not clickable"
        except Exception as e:
            error_str = str(e).lower()
            if "obscured" in error_str or "intercept" in error_str:
                return False, f"OBSCURED: #{elem_id} is covered by another element"
            elif "not visible" in error_str:
                return False, f"INVISIBLE: #{elem_id} not visible"
            elif "detached" in error_str:
                return False, f"DETACHED: #{elem_id} was removed"
            else:
                return False, f"CLICK_ERROR: {str(e)[:60]}"
    
    async def _safe_type(
        self, page: Page, locator: Locator, elem_id: int, text: str
    ) -> Tuple[bool, str]:
        """Type with error handling."""
        try:
            logger.info(f"Typing into #{elem_id}")
            await locator.fill(text, timeout=5000)
            return True, f"Typed '{text[:20]}...' into #{elem_id}"
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: #{elem_id} not ready"
        except Exception as e:
            return False, f"TYPE_ERROR: {str(e)[:60]}"
    
    async def _safe_press_enter(
        self, page: Page, locator: Locator, elem_id: int
    ) -> Tuple[bool, str]:
        """Press enter with error handling."""
        try:
            logger.info(f"Pressing Enter on #{elem_id}")
            await locator.press('Enter', timeout=5000)
            await self._smart_wait(page)
            return True, f"Pressed Enter on #{elem_id}"
        except Exception as e:
            return False, f"KEYPRESS_ERROR: {str(e)[:60]}"
    
    async def _safe_navigate(self, page: Page, url: str) -> Tuple[bool, str]:
        """Navigate with smart wait."""
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await self._smart_wait(page)
            return True, f"Navigated to {url}"
        except PlaywrightTimeoutError:
            return False, f"TIMEOUT: {url} took too long"
        except Exception as e:
            return False, f"NAVIGATION_ERROR: {str(e)[:60]}"
    
    async def _safe_scroll(self, page: Page, amount: int) -> Tuple[bool, str]:
        """Scroll with error handling."""
        try:
            direction = "down" if amount > 0 else "up"
            await page.evaluate(f"window.scrollBy(0, {amount})")
            await page.wait_for_timeout(300)
            return True, f"Scrolled {direction}"
        except Exception as e:
            return False, f"SCROLL_ERROR: {str(e)[:60]}"
    
    async def _smart_wait(self, page: Page) -> Tuple[bool, str]:
        """
        Smart wait using networkidle instead of static timeout.
        Falls back to shorter timeout if networkidle takes too long.
        """
        try:
            # Try networkidle with 3s timeout
            await page.wait_for_load_state('networkidle', timeout=3000)
            return True, "Page stable"
        except PlaywrightTimeoutError:
            # Fall back to short fixed wait
            await page.wait_for_timeout(500)
            return True, "Waited (timeout fallback)"
        except Exception:
            await page.wait_for_timeout(500)
            return True, "Waited"
    
    async def get_page_hash(self, page: Page) -> str:
        """Get hash of page content for change detection."""
        try:
            content = await page.evaluate("() => document.body.innerText.slice(0, 3000)")
            url = page.url
            return hashlib.md5(f"{url}:{content}".encode()).hexdigest()[:16]
        except Exception:
            return ""
    
    def get_element_info(self, elem_id: int) -> Optional[Dict]:
        """Get element info by ID."""
        for info in self.element_info:
            if info.get('elem_id') == elem_id:
                return info
        return None
    
    async def cleanup(self, page: Page) -> None:
        """Remove all visual overlays."""
        try:
            await page.evaluate("""
                () => {
                    document.querySelectorAll('[data-agent-tag], [data-agent-highlight]').forEach(el => el.remove());
                    document.querySelectorAll('[data-agent-id]').forEach(el => el.removeAttribute('data-agent-id'));
                }
            """)
        except Exception:
            pass

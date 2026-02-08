"""
BrowserIntelliSense - Set-of-Mark (SoM) Implementation
======================================================
This module implements the Set-of-Mark approach for web interaction.
Interactive elements are visually tagged with numeric IDs that the vision model can see.

Author: Secure Agentic Browser Project
"""

import logging
from typing import Dict, List, Tuple
from playwright.async_api import Page, Locator

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
    
    This class:
    1. Injects JavaScript to find and tag interactive elements
    2. Creates visual overlays showing numeric IDs
    3. Maps IDs to Playwright locators for action execution
    """
    
    def __init__(self):
        self.element_map: Dict[int, Locator] = {}
        self.element_info: List[Dict] = []
        logger.info("BrowserIntelliSense initialized")
    
    async def inject_script(self, page: Page) -> int:
        """
        Inject the tagging script into the page.
        
        This will:
        - Find all interactive elements
        - Filter out hidden/invisible elements
        - Assign data-agent-id attributes
        - Create visual red overlay boxes with ID numbers
        
        Args:
            page: Playwright Page object
            
        Returns:
            int: Number of elements tagged
        """
        logger.info("Injecting Set-of-Mark script...")
        
        try:
            # Execute the tagging script
            num_elements = await page.evaluate(TAGGING_SCRIPT)
            logger.info(f"Tagged {num_elements} interactive elements")
            
            # Small delay to ensure overlays are rendered
            await page.wait_for_timeout(100)
            
            return num_elements
            
        except Exception as e:
            logger.error(f"Failed to inject script: {e}")
            raise
    
    async def get_observation(self, page: Page) -> Tuple[Dict[int, Locator], str]:
        """
        Get the observation data from the page.
        
        Returns:
            Tuple containing:
            - element_map: Dict mapping ID -> Playwright Locator
            - element_text: Clean text listing of elements
        """
        logger.info("Extracting observation data...")
        
        # Clear previous mappings
        self.element_map = {}
        self.element_info = []
        
        # Get all tagged elements
        tagged_elements = await page.query_selector_all('[data-agent-id]')
        
        element_lines = []
        
        for elem in tagged_elements:
            # Get the ID
            elem_id = await elem.get_attribute('data-agent-id')
            if not elem_id:
                continue
            
            elem_id = int(elem_id)
            
            # Get element info
            tag_name = await elem.evaluate('el => el.tagName.toLowerCase()')
            text_content = await elem.evaluate('el => (el.innerText || el.value || el.placeholder || "").trim()')
            elem_type = await elem.get_attribute('type') or tag_name
            
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
                'text': text_content
            }
            self.element_info.append(info)
            
            # Create text line
            if text_content:
                line = f"[{elem_id}] {elem_type}: \"{text_content}\""
            else:
                line = f"[{elem_id}] {elem_type}"
            
            element_lines.append(line)
        
        # Create text observation
        element_text = "\n".join(element_lines)
        
        logger.info(f"Extracted {len(self.element_map)} elements")
        
        return self.element_map, element_text
    
    async def execute_action(
        self,
        page: Page,
        action_dict: Dict,
        element_map: Dict[int, Locator]
    ) -> bool:
        """
        Execute an action based on the action dictionary.
        
        Args:
            page: Playwright Page object
            action_dict: Dict with 'action' and 'id' keys
            element_map: Mapping of IDs to Locators
            
        Returns:
            bool: True if action succeeded
        """
        action_type = action_dict.get('action', '').lower()
        element_id = action_dict.get('id')
        
        if element_id is None:
            logger.error("No element ID provided in action")
            return False
        
        # Convert to int if string
        if isinstance(element_id, str):
            try:
                element_id = int(element_id)
            except ValueError:
                logger.error(f"Invalid element ID: {element_id}")
                return False
        
        # Get locator
        if element_id not in element_map:
            logger.error(f"Element ID {element_id} not found in element map")
            return False
        
        locator = element_map[element_id]
        
        try:
            if action_type == 'click':
                logger.info(f"Clicking element {element_id}")
                await locator.click(timeout=5000)
                await page.wait_for_timeout(500)  # Wait for page to respond
                return True
            
            elif action_type == 'type':
                text = action_dict.get('value', '')
                logger.info(f"Typing '{text}' into element {element_id}")
                await locator.fill(text)
                return True
            
            elif action_type == 'press_enter':
                logger.info(f"Pressing Enter on element {element_id}")
                await locator.press('Enter')
                await page.wait_for_timeout(1000)  # Wait for navigation
                return True
            
            else:
                logger.error(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False
    
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
            logger.error(f"Cleanup failed: {e}")

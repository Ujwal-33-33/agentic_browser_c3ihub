"""
DOM Distiller - Reduce Token Count via Smart DOM Extraction
============================================================
Extracts only interactive and meaningful elements from the page
using JavaScript DOM traversal, reducing tokens from ~50k to <2k.
"""

from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class DOMDistiller:
    """
    Distills web pages into compact, LLM-friendly representations
    by extracting only interactive and text elements.
    """
    
    # JavaScript code to extract distilled DOM
    EXTRACTION_SCRIPT = """
    () => {
        const elements = [];
        let idCounter = 0;
        
        // Interactive element selectors
        const interactiveSelectors = [
            'a[href]', 'button', 'input', 'select', 'textarea',
            '[role="button"]', '[role="link"]', '[role="textbox"]',
            '[role="searchbox"]', '[role="checkbox"]', '[role="radio"]',
            '[onclick]', '[tabindex]'
        ];
        
        // Text content selectors
        const textSelectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'span'
        ];
        
        // Get all interactive elements
        interactiveSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (!el.offsetParent && el.tagName !== 'INPUT') return; // Skip hidden
                
                const text = (el.innerText || el.value || el.placeholder || el.title || '').trim();
                if (!text && el.tagName !== 'INPUT' && el.tagName !== 'BUTTON') return;
                
                const role = el.getAttribute('role') || el.tagName.toLowerCase();
                const type = el.getAttribute('type') || role;
                
                elements.push({
                    id: ++idCounter,
                    type: type,
                    text: text.slice(0, 100), // Limit length
                    interactive: true
                });
            });
        });
        
        // Get important text content
        const seenTexts = new Set();
        textSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (!el.offsetParent) return; // Skip hidden
                
                const text = el.innerText.trim();
                if (!text || text.length < 3 || seenTexts.has(text)) return;
                if (text.length > 200) return; // Skip very long paragraphs
                
                seenTexts.add(text);
                
                const role = el.tagName.toLowerCase();
                
                elements.push({
                    id: elements.filter(e => e.interactive).length > 0 ? null : ++idCounter,
                    type: role,
                    text: text.slice(0, 150),
                    interactive: false
                });
            });
        });
        
        return elements;
    }
    """
    
    def __init__(self):
        """Initialize the distiller."""
        pass
    
    async def get_simplified_state(self, page) -> str:
        """
        Extract simplified page state from DOM.
        
        Args:
            page: Playwright page object
            
        Returns:
            Compact string representation of the page (~2k tokens)
        """
        try:
            logger.info("Distilling page DOM...")
            
            # Execute extraction script
            elements = await page.evaluate(self.EXTRACTION_SCRIPT)
            
            if not elements:
                return "Error: No elements extracted"
            
            # Format into compact string
            output = self._format_elements(elements)
            
            tokens_estimate = len(output) // 4
            logger.info(f"Distilled {len(elements)} elements (~{tokens_estimate} tokens)")
            
            return output
            
        except Exception as e:
            logger.error(f"Error distilling page: {e}")
            return f"Error: {str(e)}"
    
    def _format_elements(self, elements: List[Dict]) -> str:
        """
        Format extracted elements into compact string.
        
        Args:
            elements: List of extracted elements
            
        Returns:
            Formatted string
        """
        lines = []
        lines.append("=== PAGE ELEMENTS ===\n")
        
        # Separate interactive and content
        interactive = [e for e in elements if e.get('interactive')]
        content = [e for e in elements if not e.get('interactive')]
        
        # Interactive elements first (these have IDs)
        if interactive:
            lines.append("--- Interactive Elements ---")
            for elem in interactive[:100]:  # Limit to 100
                elem_type = elem['type'].capitalize()
                text = elem['text'] or '(no text)'
                elem_id = elem['id']
                
                if len(text) > 60:
                    text = text[:57] + "..."
                
                lines.append(f"[{elem_type}] \"{text}\" (ID: {elem_id})")
            lines.append("")
        
        # Content elements (no IDs needed)
        if content:
            lines.append("--- Page Content ---")
            for elem in content[:50]:  # Limit to 50
                elem_type = elem['type'].upper()
                text = elem['text']
                
                if len(text) > 80:
                    text = text[:77] + "..."
                
                lines.append(f"{elem_type}: {text}")
            lines.append("")
        
        lines.append(f"Total: {len(interactive)} interactive, {len(content)} content elements")
        
        return '\n'.join(lines)


# Example integration
async def demo_distiller(page):
    """Demo the distiller on a page."""
    distiller = DOMDistiller()
    
    # Get simplified state
    simplified = await distiller.get_simplified_state(page)
    
    print("\n" + "=" * 70)
    print("DISTILLED PAGE STATE")
    print("=" * 70)
    print(simplified)
    print("=" * 70 + "\n")
    
    # Estimate token reduction
    original_text = await page.evaluate("() => document.body.innerText")
    original_tokens = len(original_text) // 4
    distilled_tokens = len(simplified) // 4
    
    print(f"Original: ~{original_tokens:,} tokens")
    print(f"Distilled: ~{distilled_tokens:,} tokens")
    print(f"Reduction: {100 * (1 - distilled_tokens/original_tokens):.1f}%\n")

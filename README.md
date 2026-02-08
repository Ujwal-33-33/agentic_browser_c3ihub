# Secure Agentic Browser with Ollama

A secure, autonomous web browser powered by local Ollama LLM with advanced DOM distillation and visual element tagging.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run the agent
python main.py
```

## 📁 Project Structure

```
secure-agentic-browser/
├── agent.py              # Main OllamaAgent class (Observe-Think-Act loop)
├── browser_sense.py      # Set-of-Mark (SoM) visual tagging system
├── distiller.py          # DOM Distiller for token reduction (~95%)
├── main.py              # Entry point and examples
├── requirements.txt      # Python dependencies
├── .env                 # Configuration (Ollama settings)
├── docs/                # Documentation and guides
│   ├── DISTILLER_INTEGRATION.md
│   ├── OLLAMA_REFACTORING.md
│   ├── SOM_README.md
│   └── ...test results and reports
└── tests/               # Test scripts and examples
    ├── test_*.py        # Various test scripts
    ├── som_demo.py      # SoM system demo
    └── ...screenshots and test outputs
```

## 🎯 Core Components

### 1. **agent.py** - Ollama Agent
- Async Observe-Think-Act loop
- OpenAI-compatible Ollama integration
- Security layer with scan/validate hooks
- Support for multiple actions (click, type, navigate, etc.)

### 2. **browser_sense.py** - Set-of-Mark (SoM)
- Visual element tagging with red numbered boxes
- ID-to-locator mapping for precise interactions
- Action execution engine (click, type, press_enter)
- Cleanup utilities

### 3. **distiller.py** - DOM Distiller
- **95% token reduction** (50k → 2k tokens)
- Extracts only interactive + text elements
- Smart filtering using JavaScript DOM traversal
- Preserves full navigation capability

## 🔧 Configuration

Edit `.env` file:
```bash
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3
```

## 📊 Key Features

✅ **Local LLM** - No API costs, runs on Ollama  
✅ **95% Token Reduction** - DOM Distiller filters to essentials  
✅ **Visual Tagging** - SoM system with red numbered boxes  
✅ **Security Layer** - Scan observations, validate actions  
✅ **Multi-Step Tasks** - Complex autonomous workflows  
✅ **Screenshot Support** - Base64 encoded for vision models  

## 🧪 Testing

Run tests from the `tests/` directory:

```bash
# Test DOM distiller
python tests/test_distiller.py

# Test SoM interactions
python tests/test_som_interactions.py

# Test complex multi-step agent
python tests/test_complex_agent.py

# Test Wikipedia extraction
python tests/test_wikipedia_complete.py
```

## 📈 Performance

**Token Reduction (Wikipedia page):**
- Original: ~22,778 tokens
- Distilled: ~1,209 tokens
- **Reduction: 94.7%** (18.8x smaller!)

**Capabilities Verified:**
- ✅ Page navigation
- ✅ Element detection
- ✅ Form filling (type actions)
- ✅ Clicks (buttons, links)
- ✅ Information extraction
- ✅ Multi-step workflows

## 🔍 Example Usage

```python
from agent import OllamaAgent

# Create agent
agent = OllamaAgent(headless=False)

# Run autonomous task
await agent.run(
    goal="Search Wikipedia for 'Virat Kohli' and extract his information"
)
```

## 📚 Documentation

See `docs/` folder for detailed guides:
- **DISTILLER_INTEGRATION.md** - How to integrate DOM distiller
- **OLLAMA_REFACTORING.md** - Ollama integration details
- **SOM_README.md** - Set-of-Mark system guide
- **Test Results** - Various validation reports

## 🛡️ Security

The security layer provides hooks for:
- `scan_observation()` - Scan page content before sending to LLM
- `validate_action()` - Validate LLM actions before execution

*Note: Security logic placeholders currently in place for implementation.*

## 🎨 Architecture

```
┌─────────────────────────────────────────────────────┐
│                  OLLAMA AGENT                        │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ OBSERVE  │ -> │  THINK   │ -> │   ACT    │     │
│  │          │    │          │    │          │     │
│  │ Browser  │    │  Ollama  │    │ Executor │     │
│  │ Distiller│    │  LLM     │    │ Actions  │     │
│  │ SoM      │    │  (JSON)  │    │ Click    │     │
│  └──────────┘    └──────────┘    │ Type     │     │
│                                   │ Navigate │     │
│                                   └──────────┘     │
│                                                      │
│  Security Layer: scan() + validate()                │
└─────────────────────────────────────────────────────┘
```

## 🚧 Future Enhancements

- [ ] Integrate llava vision model for visual grounding
- [ ] Implement full security scanning logic
- [ ] Add conversation memory/context
- [ ] Multi-page workflows
- [ ] Error recovery strategies

## 📝 License

MIT License - See LICENSE file for details

---

**Built with**: Playwright + Ollama + Python  
**LLM**: llama3 (text-only, vision models supported)  
**Author**: Secure Agentic Browser Team

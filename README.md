# Secure Agentic Browser

Web browser automation using Ollama LLM with visual element tagging.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Structure

- `agent.py` - Main agent (Observe->Think->Act loop)
- `browser_sense.py` - Visual element tagging (Set-of-Mark)
- `distiller.py` - DOM filtering for token reduction  
- `security.py` - Security checks (whitelist, PII detection)
- `main.py` - Entry point

## Features

- Local LLM (no API costs)
- ~95% token reduction via DOM distilling
- Visual SoM tagging with element IDs
- Security layer (domain whitelist, credential protection)
- Multi-step autonomous tasks

## Config

Edit `.env`:
```bash
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5-coder:7b
```

## Usage

```python
from agent import OllamaAgent

agent = OllamaAgent(headless=False)
await agent.run(goal="Search Wikipedia for Python")
```

## Testing

```bash
python test_comprehensive.py
python demo_script.py  # for video demos
```

## Architecture

```
OBSERVE (browser + SoM) -> THINK (LLM) -> ACT (execute) -> VERIFY (page change)
```

Security checks run before actions.

## Notes

- Works with any Ollama model
- Handles password fields, unknown domains (blocked/warned)
- Auto-submit on repeated type actions (handles stubborn models)

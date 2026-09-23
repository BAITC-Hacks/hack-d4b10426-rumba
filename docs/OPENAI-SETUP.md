# OpenAI Setup

Career Quest can operate in two recommendation modes:

1. OpenAI-assisted reranking when OPENAI_API_KEY is available.
2. Deterministic fallback when the key is absent or the provider fails.

## Windows PowerShell

Run commands from the repository root:
```powershell
$env:OPENAI_API_KEY="YOUR_API_KEY"
python -m career_quest.api
```

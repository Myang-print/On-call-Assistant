# Kimi API Smoke Test

This folder is isolated from the application runtime. It is only for manually
checking whether the local Python environment can call the Kimi/Moonshot API.

It does not import app code and is not part of the pytest suite.

## Setup

Install the OpenAI-compatible SDK in your active virtual environment:

```powershell
pip install --upgrade "openai>=1.0"
```

Set the API key before running:

```powershell
$env:MOONSHOT_API_KEY="sk-xxxx"
$env:MOONSHOT_BASE_URL="https://api.moonshot.cn/v1"
$env:MOONSHOT_MODEL="kimi-k2.6"
```

## Run

```powershell
python kimi_api_smoke/run_kimi_smoke.py
```

Expected result: the script prints the selected base URL/model, dispatches one
minimal chat completion request, and prints the assistant response.

If the call fails, the script prints the exception type and error message without
printing the API key.

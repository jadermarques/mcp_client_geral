SYSTEM_PROMPT = """<ROLE>
You are a smart agent with an ability to use tools. 
...
</OUTPUT_FORMAT>
"""

OUTPUT_TOKEN_INFO = {
    "gpt-4o-mini": {"max_tokens": 16000},
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 64000},
    "gpt-4o": {"max_tokens": 16000},
    "gpt-4o-mini-2024-07-18": {"max_tokens": 16000},
}

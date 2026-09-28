"""Tiny Ollama client shared by all modules."""
import json
import os
import re
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:7b")


def chat(system: str, user: str, json_mode: bool = False, timeout: int = 300) -> str:
    payload = {"model": CHAT_MODEL, "stream": False, "options": {"temperature": 0},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        payload["format"] = "json"
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"].strip()


def parse_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in ``` fences or added text around it."""
    text = re.sub(r"```(json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError(f"Model did not return JSON: {text[:200]}")
        return json.loads(m.group(0))

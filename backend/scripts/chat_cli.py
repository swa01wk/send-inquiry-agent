#!/usr/bin/env python3
"""Minimal terminal client for chat SSE against a running backend."""

from __future__ import annotations

import json
import os

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=120.0) as client:
        session = client.post("/api/sessions").json()
        session_id = session["session_id"]
        print(f"Session {session_id}")
        for message in session.get("messages", []):
            print(f"assistant: {message['text']}")
        print("Type a message (empty line to quit).\n")

        while True:
            try:
                text = input("you: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                break
            with client.stream(
                "POST",
                f"/api/sessions/{session_id}/chat",
                json={"type": "message", "text": text},
            ) as response:
                response.raise_for_status()
                current = ""
                for line in response.iter_lines():
                    if line.startswith("event:"):
                        current = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line.split(":", 1)[1])
                        if current == "token":
                            print(data.get("text", ""), end="", flush=True)
                        elif current == "done":
                            print(f"\n[done phase={data.get('phase')}]")
                        elif current == "error":
                            print(f"\n[error {data}]")
                print()


if __name__ == "__main__":
    main()

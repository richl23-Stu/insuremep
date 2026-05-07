import os
import sys
from google import genai
from google.genai import types

def my_test_tool(x: int) -> int:
    """Returns x + 1"""
    return x + 1

try:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(tools=[my_test_tool])
    )
    resp = chat.send_message("What is my_test_tool(5)?")
    print("RESPONSE:", resp.text)
except Exception as e:
    print("ERROR:", str(e))

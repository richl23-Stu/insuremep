import os
import sys
from google import genai

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    if len(sys.argv) > 1:
        # One-off query: python gemini_chat.py "What is 2+2?"
        prompt = " ".join(sys.argv[1:])
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        print(f"\nGemini: {response.text}")
    else:
        # Interactive mode
        print("--- Gemini Chat Mode (Type 'exit' to quit) ---")
        while True:
            try:
                user_input = input("\nYou: ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_input
                )
                print(f"\nGemini: {response.text}")
            except EOFError:
                break
            except Exception as e:
                print(f"\nError: {e}")

if __name__ == "__main__":
    main()

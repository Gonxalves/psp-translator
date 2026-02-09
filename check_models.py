"""Check available Claude models"""
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# Try a simple API call to see what models work
test_models = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-latest",
]

print("Testing available Claude models...")
print("-" * 60)

for model in test_models:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"[OK] {model} - Available")
    except anthropic.NotFoundError:
        print(f"[404] {model} - Not found")
    except Exception as e:
        print(f"[ERROR] {model} - {type(e).__name__}: {str(e)[:50]}")

print("\n" + "=" * 60)
print("Recommendation: Use the first [OK] model listed above")

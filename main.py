import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()  # reads .env and injects HF_TOKEN into os.environ

MODEL = "Qwen/Qwen2.5-7B-Instruct"  # free tier, 30K req/month

client = InferenceClient(
    model=MODEL,
    token=os.getenv("HF_TOKEN"),  # reads the token from .env
)

response = client.chat_completion(
    messages=[
        {
            "role": "system",
            "content": (
                "You are Scout, the first agent of Terramon — "
                "a system where real-world objects become intelligent entities. "
                "You observe the physical world and report what you find."
            ),
        },
        {
            "role": "user",
            "content": "Describe your mission in one sentence.",
        },
    ],
    max_tokens=80,
    temperature=0.7,
)

print("🌍 Scout says:", response.choices[0].message.content)
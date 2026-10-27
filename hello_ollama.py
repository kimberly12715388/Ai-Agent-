import ollama

response = ollama.chat(
    model="qwen3.5:4b",
    messages=[{"role": "user", "content": "Say hello in five words."}],
    # Skip the model's step-by-step reasoning so this check is quick.
    think=False,
)

print(response.message.content)
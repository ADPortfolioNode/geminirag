import openai

openai.api_key = "<OPENAI_API_KEY>"

try:
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="Hello, world!",
        max_tokens=5
    )
    print("API Key is valid. Response:", response.choices[0].text.strip())
except Exception as e:
    print("Error:", e)
import requests

LLM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"

def send_to_llm(messages):
    payload = {
        "model": "mistral-7b-instruct-v0.3",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False,
    }
    response = requests.post(LLM_API_URL, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    return "Error communicating with LLM"
from llm_service import send_to_llm

def translate_text(text, target_language):
    if target_language.lower() == "english":
        return text

    messages = [{
        "role": "user",
        "content": f"Translate the following text into {target_language} and only the target language. Do not include any extra text or explanations. Only translate the text provided. Do not translate names, numerical values, or locations. Text: {text}"
    }]
    return send_to_llm(messages)

def translate_to_english(text):
    messages = [{
        "role": "user",
        "content": f"Translate the following text into English. If the text is already in English or does not require translation (e.g., names, numbers, locations), return the original text. Text: {text}"
    }]
    return send_to_llm(messages)
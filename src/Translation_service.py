from llm_service import send_to_llm

def translate_text(text, target_language):
    if target_language.lower() == "english":
        return text

    prompt = (
        f"You are a professional translator. Please translate the following text into {target_language} accurately, "
        "preserving the original tone, context, and formatting. Do not translate proper names, numerical values, or locations. "
        "Return only the translated text with no extra commentary or explanations.\n\n"
        f"Text: {text}"
    )
    messages = [{"role": "user", "content": prompt}]
    return send_to_llm(messages)

def translate_to_english(text):
    prompt = (
        "You are a professional translator. Please translate the following text into English accurately, "
        "preserving the original tone, context, and formatting. If the text is already in English or does not require translation "
        "(for example, proper names, numbers, or locations), return the text unchanged. "
        "Return only the translated text without any extra commentary or explanations.\n\n"
        f"Text: {text}"
    )
    messages = [{"role": "user", "content": prompt}]
    return send_to_llm(messages)

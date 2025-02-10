# LLMcon.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import os
import uuid

app = Flask(__name__)
CORS(app)

LLM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"

# Store conversation state
conversation_state = {
    "questions": [],  # List of questions from the file
    "current_question_index": 0,  # Index of the current question being asked
    "answers": [],  # List of user answers
    "file_processed": False,  # Whether the file has been processed
    "in_question_mode": False,  # Whether the LLM is in question-answering mode
    "awaiting_answer": False,  # Whether the backend is waiting for an answer to the current question
    "conversation_history": [],  # List of messages in the conversation
    "language": "english",  # Default language
}

def send_to_llm(messages):
    """
    Sends a message to the LLM and returns the response.
    """
    payload = {
        "model": "hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF/llama-3.2-1b-instruct-q8_0.gguf",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False,
    }
    response = requests.post(LLM_API_URL, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    return "Error communicating with LLM"

def translate_text(text, target_language):
    """
    Translates text into the specified target language using the LLM.
    Only translates if the target language is not English.
    Ensures the LLM only outputs the translated text without extra explanations.
    """
    if target_language.lower() == "english":
        return text  # No translation needed for English

    # Prompt the LLM to translate the text into the target language
    messages = [{
        "role": "user",
        "content": f"Translate the following text into {target_language} and only the target language. Do not include any extra text or explanations. Only translate the text provided. Do not translate names, numerical values, or locations. Text: {text}"
    }]
    return send_to_llm(messages)

def translate_to_english(text):
    """
    Translates text into English using the LLM.
    Only translates if the text is not already in English.
    """
    # Prompt the LLM to translate the text into English
    messages = [{
        "role": "user",
        "content": f"Translate the following text into English. If the text is already in English or does not require translation (e.g., names, numbers, locations), return the original text. Text: {text}"
    }]
    return send_to_llm(messages)

def generate_qa_file(questions, answers):
    """
    Generates a text file with questions and answers.
    Returns the path to the generated file.
    """
    # Create a unique filename
    filename = f"qa_{uuid.uuid4().hex}.txt"
    filepath = os.path.join("temp", filename)

    # Ensure the temp directory exists
    os.makedirs("temp", exist_ok=True)

    # Write questions and answers to the file
    with open(filepath, "w", encoding="utf-8") as file:
        for i, (question, answer) in enumerate(zip(questions, answers)):
            file.write(f"Q{i + 1}: {question}\nA{i + 1}: {answer}\n\n")

    return filepath

@app.route("/chat", methods=["POST"])
def chat():
    global conversation_state

    data = request.json
    user_message = data.get("message", "")
    language = data.get("language", "english")  # Get the selected language

    if not user_message and conversation_state["awaiting_answer"]:
        return jsonify({"error": "Message cannot be empty"}), 400

    if conversation_state["in_question_mode"]:
        if conversation_state["awaiting_answer"]:
            # Translate the user's answer back into English if necessary
            if language.lower() != "english":
                translated_answer = translate_to_english(user_message)
            else:
                translated_answer = user_message

            # Log the user's answer to the current question
            conversation_state["answers"].append(translated_answer)
            conversation_state["awaiting_answer"] = False  # Reset the flag

            # Add the user's answer to the conversation history
            conversation_state["conversation_history"].append({"role": "user", "content": user_message})

            # Check if all questions have been answered
            if conversation_state["current_question_index"] >= len(conversation_state["questions"]):
                # All questions answered, generate a file with questions and answers
                qa_filepath = generate_qa_file(conversation_state["questions"], conversation_state["answers"])

                # Generate a download link for the file
                download_link = f"/download/{os.path.basename(qa_filepath)}"

                # Reset question-answering mode
                conversation_state["in_question_mode"] = False
                conversation_state["questions"] = []
                conversation_state["current_question_index"] = 0
                conversation_state["answers"] = []

                # Add the summary and download link to the conversation history
                summary = "Here are the questions and answers:\n"
                for i, (question, answer) in enumerate(zip(conversation_state["questions"], conversation_state["answers"])):
                    summary += f"{i + 1}. Q: {question}\n   A: {answer}\n"

                summary += f"\nYou can download the questions and answers here: {download_link}"
                conversation_state["conversation_history"].append({"role": "assistant", "content": summary})

                return jsonify({"reply": summary, "download_link": download_link})

            # Get the next question
            question = conversation_state["questions"][conversation_state["current_question_index"]]
            conversation_state["current_question_index"] += 1
            conversation_state["awaiting_answer"] = True  # Set the flag to expect an answer

            # Add the question to the conversation history
            conversation_state["conversation_history"].append({"role": "assistant", "content": question})

            return jsonify({"reply": question})
        else:
            # Send the current question (no answer expected yet)
            question = conversation_state["questions"][conversation_state["current_question_index"]]
            conversation_state["awaiting_answer"] = True  # Set the flag to expect an answer

            # Add the question to the conversation history
            conversation_state["conversation_history"].append({"role": "assistant", "content": question})

            return jsonify({"reply": question})
    else:
        # Normal chat mode
        # Add the user's message to the conversation history
        conversation_state["conversation_history"].append({"role": "user", "content": user_message})

        # Send the entire conversation history to the LLM
        llm_response = send_to_llm(conversation_state["conversation_history"])

        # Add the LLM's response to the conversation history
        conversation_state["conversation_history"].append({"role": "assistant", "content": llm_response})

        return jsonify({"reply": llm_response})

@app.route("/upload", methods=["POST"])
def upload():
    global conversation_state

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    file_content = file.read().decode("utf-8")  # Read and decode file content

    # Get the selected language from the request headers
    language = request.headers.get("Language", "english")
    conversation_state["language"] = language

    # Reset conversation state for question-answering mode
    conversation_state["questions"] = file_content.splitlines()  # Split file content into questions
    conversation_state["current_question_index"] = 0
    conversation_state["answers"] = []
    conversation_state["file_processed"] = True
    conversation_state["in_question_mode"] = True  # Enter question-answering mode
    conversation_state["awaiting_answer"] = False  # No answer expected yet

    # Translate the questions into the specified language if not English
    if language.lower() != "english":
        for i, question in enumerate(conversation_state["questions"]):
            conversation_state["questions"][i] = translate_text(question, language)

    # Send the first question immediately after upload
    if conversation_state["questions"]:
        question = conversation_state["questions"][conversation_state["current_question_index"]]
        conversation_state["current_question_index"] += 1
        conversation_state["awaiting_answer"] = True  # Set the flag to expect an answer

        # Add the question to the conversation history
        conversation_state["conversation_history"].append({"role": "assistant", "content": question})

        return jsonify({"reply": question})
    else:
        return jsonify({"error": "No questions found in the file"}), 400

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    """
    Allows the user to download the generated Q&A file.
    """
    filepath = os.path.join("temp", filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    app.run(debug=True, port=5000)
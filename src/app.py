from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from conversation_state import conversation_state
from llm_service import send_to_llm
from Translation_service import translate_text, translate_to_english
from file_download import generate_qa_file
import os

app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    language = data.get("language", "english")

    if not user_message and conversation_state["awaiting_answer"]:
        return jsonify({"error": "Message cannot be empty"}), 400

    if conversation_state["in_question_mode"]:
        if conversation_state["awaiting_answer"]:
            if language.lower() != "english":
                translated_answer = translate_to_english(user_message)
            else:
                translated_answer = user_message

            conversation_state["answers"].append(translated_answer)
            conversation_state["awaiting_answer"] = False
            conversation_state["conversation_history"].append({"role": "user", "content": user_message})

            if conversation_state["current_question_index"] >= len(conversation_state["questions"]):
                qa_filepath = generate_qa_file(conversation_state["questions"], conversation_state["answers"])
                download_link = f"/download/{os.path.basename(qa_filepath)}"

                conversation_state["in_question_mode"] = False
                conversation_state["questions"] = []
                conversation_state["current_question_index"] = 0
                conversation_state["answers"] = []

                summary = "Here are the questions and answers:\n"
                for i, (question, answer) in enumerate(zip(conversation_state["questions"], conversation_state["answers"])):
                    summary += f"{i + 1}. Q: {question}\n   A: {answer}\n"

                summary += f"\nYou can download the questions and answers here: {download_link}"
                conversation_state["conversation_history"].append({"role": "assistant", "content": summary})

                return jsonify({"reply": summary, "download_link": download_link})

            question = conversation_state["questions"][conversation_state["current_question_index"]]
            conversation_state["current_question_index"] += 1
            conversation_state["awaiting_answer"] = True
            conversation_state["conversation_history"].append({"role": "assistant", "content": question})

            return jsonify({"reply": question})
        else:
            question = conversation_state["questions"][conversation_state["current_question_index"]]
            conversation_state["awaiting_answer"] = True
            conversation_state["conversation_history"].append({"role": "assistant", "content": question})

            return jsonify({"reply": question})
    else:
        conversation_state["conversation_history"].append({"role": "user", "content": user_message})
        llm_response = send_to_llm(conversation_state["conversation_history"])
        conversation_state["conversation_history"].append({"role": "assistant", "content": llm_response})

        return jsonify({"reply": llm_response})

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    file_content = file.read().decode("utf-8")

    language = request.headers.get("Language", "english")
    conversation_state["language"] = language

    conversation_state["questions"] = file_content.splitlines()
    conversation_state["current_question_index"] = 0
    conversation_state["answers"] = []
    conversation_state["file_processed"] = True
    conversation_state["in_question_mode"] = True
    conversation_state["awaiting_answer"] = False

    if language.lower() != "english":
        for i, question in enumerate(conversation_state["questions"]):
            conversation_state["questions"][i] = translate_text(question, language)

    if conversation_state["questions"]:
        question = conversation_state["questions"][conversation_state["current_question_index"]]
        conversation_state["current_question_index"] += 1
        conversation_state["awaiting_answer"] = True
        conversation_state["conversation_history"].append({"role": "assistant", "content": question})

        return jsonify({"reply": question})
    else:
        return jsonify({"error": "No questions found in the file"}), 400

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    filepath = os.path.join("temp", filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    app.run(debug=False, port=5000)
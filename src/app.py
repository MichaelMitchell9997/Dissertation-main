from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from conversation_state import conversation_state
from llm_service import send_to_llm
from Translation_service import translate_text, translate_to_english
from utils.pdf_processor import extract_form_fields_from_pdf
from file_download import generate_qa_file
from PyPDF2 import PdfReader, PdfWriter
import os
import re
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

def extract_question_number(question):
    """
    Extracts the numeric part from a question string.
    For example, "Q3 | Date of birth" returns 3.
    If not found, returns infinity to push unsortable items to the end.
    """
    match = re.search(r"Q\s*(\d+)", question)
    if match:
        return int(match.group(1))
    return float('inf')

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

            # Update the answer for the current question (answers align with original keys)
            index = conversation_state["current_question_index"] - 1
            if index < len(conversation_state["answers"]):
                conversation_state["answers"][index] = translated_answer
            else:
                conversation_state["answers"].append(translated_answer)
            
            conversation_state["awaiting_answer"] = False
            conversation_state["conversation_history"].append({"role": "user", "content": user_message})

            # If all questions have been answered, generate the filled PDF or QA file.
            if conversation_state["current_question_index"] >= len(conversation_state["questions"]):
                # Use the original field names (keys) to populate the PDF.
                form_data = dict(zip(conversation_state["original_questions"], conversation_state["answers"]))

                if conversation_state.get("original_pdf_path"):
                    input_pdf_path = conversation_state["original_pdf_path"]
                    output_pdf_path = os.path.join("temp", "filled_form.pdf")
                    
                    try:
                        populate_pdf_form(input_pdf_path, output_pdf_path, form_data)
                    except Exception as e:
                        logging.error(f"Error populating PDF: {e}")
                        return jsonify({"error": "Error populating PDF form"}), 500

                    download_link = f"/download/{os.path.basename(output_pdf_path)}"
                    summary = "Your form has been filled. You can download the completed PDF here: " + download_link
                else:
                    qa_filepath = generate_qa_file(conversation_state["original_questions"], conversation_state["answers"])
                    download_link = f"/download/{os.path.basename(qa_filepath)}"
                    summary = "Here are the questions and answers:\n"
                    for i, (question, answer) in enumerate(zip(conversation_state["original_questions"], conversation_state["answers"])):
                        summary += f"{i + 1}. Q: {question}\n   A: {answer}\n"
                    summary += f"\nYou can download the file here: {download_link}"

                # Reset conversation state for a new session.
                conversation_state["in_question_mode"] = False
                conversation_state["original_questions"] = []
                conversation_state["questions"] = []
                conversation_state["current_question_index"] = 0
                conversation_state["answers"] = []
                conversation_state["original_pdf_path"] = ""
                conversation_state["conversation_history"].append({"role": "assistant", "content": summary})

                return jsonify({"reply": summary, "download_link": download_link})

            # Ask the next question using the translated version.
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
    filename = file.filename

    try:
        if filename.endswith(".pdf"):
            os.makedirs("temp", exist_ok=True)
            file_path = os.path.join("temp", filename)
            file.save(file_path)
            
            # Extract form fields/questions from the PDF.
            with open(file_path, "rb") as f:
                form_fields = extract_form_fields_from_pdf(f)
            
            conversation_state["original_pdf_path"] = file_path
            file_content = "\n".join([f"{key}: {value}" for key, value in form_fields.items()])
        else:
            file_content = file.read().decode("utf-8")
            form_fields = {}

        language = request.headers.get("Language", "english")
        conversation_state["language"] = language

        # Sort original questions by their Q number.
        original_questions = list(form_fields.keys())
        original_questions.sort(key=extract_question_number)
        # Store the original keys to use when populating the PDF.
        conversation_state["original_questions"] = original_questions
        # Initialize answers based on the sorted original questions.
        conversation_state["answers"] = [form_fields[q] for q in original_questions]

        # Create translated questions for the user interface.
        if language.lower() != "english":
            translated_questions = []
            for q in original_questions:
                translated_questions.append(translate_text(q, language))
            conversation_state["questions"] = translated_questions
        else:
            conversation_state["questions"] = original_questions

        conversation_state["current_question_index"] = 0
        conversation_state["file_processed"] = True
        conversation_state["in_question_mode"] = True
        conversation_state["awaiting_answer"] = False

        if conversation_state["questions"]:
            question = conversation_state["questions"][conversation_state["current_question_index"]]
            conversation_state["current_question_index"] += 1
            conversation_state["awaiting_answer"] = True
            conversation_state["conversation_history"].append({"role": "assistant", "content": question})
            return jsonify({"reply": question})
        else:
            return jsonify({"error": "No questions found in the file"}), 400

    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return jsonify({"error": "Error processing file"}), 500
    

@app.route("/rephrase", methods=["POST"])
def rephrase_question():
    # For debugging, log the current conversation state
    logging.info("Rephrase endpoint called")
    logging.info(f"Current conversation_state: {conversation_state}")
    
    # Determine the index of the question to rephrase.
    # If the current question has not yet been answered, it should be at current_question_index - 1.
    index = conversation_state["current_question_index"] - 1
    
    if index < 0 or index >= len(conversation_state["questions"]):
        logging.error("No valid question available for rephrasing.")
        return jsonify({"error": "No question available for rephrasing."}), 400

    # Get the question that was shown to the user
    current_question = conversation_state["questions"][index]
    logging.info(f"Current question to rephrase: {current_question}")

    # Construct the prompt to ask the LLM to simplify and explain the question
    prompt = (
        "You are a helpful assistant who can simplify language. "
        "Rephrase the following question in simpler terms and include a brief explanation of what the question is asking. "
        "Make sure the rephrased version is clear and easy to understand for someone who might struggle with the original phrasing.\n\n"
        f"Question: {current_question}"
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        rephrased_question = send_to_llm(messages)
        logging.info(f"Rephrased question: {rephrased_question}")
        return jsonify({"reply": rephrased_question})
    except Exception as e:
        logging.error(f"Error in rephrase endpoint: {e}")
        return jsonify({"error": "Failed to rephrase the question."}), 500

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    filepath = os.path.join("temp", filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404
    

@app.route("/generate_filled_pdf", methods=["POST"])
def generate_filled_pdf():
    try:
        # Use the original field names to build form_data.
        form_data = dict(zip(conversation_state["original_questions"], conversation_state["answers"]))
        input_pdf_path = conversation_state.get("original_pdf_path", "path/to/original_form.pdf")
        output_pdf_path = os.path.join("temp", "filled_form.pdf")
        
        populate_pdf_form(input_pdf_path, output_pdf_path, form_data)
        return send_file(output_pdf_path, as_attachment=True)
    except Exception as e:
        logging.error(f"Error generating filled PDF: {e}")
        return jsonify({"error": "Error generating filled PDF"}), 500


def populate_pdf_form(input_pdf_path, output_pdf_path, form_data):
    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # Update form fields on every page.
        for page in writer.pages:
            writer.update_page_form_field_values(page, form_data)

        with open(output_pdf_path, "wb") as output_pdf:
            writer.write(output_pdf)

        return output_pdf_path
    except Exception as e:
        raise RuntimeError(f"Failed to populate PDF form: {e}")


if __name__ == "__main__":
    app.run(debug=False, port=5000)

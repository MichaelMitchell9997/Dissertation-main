from pdfminer.high_level import extract_text
from io import BytesIO
from PyPDF2 import PdfReader
from llm_service import send_to_llm  # make sure this import is available

def extract_text_from_pdf(pdf_file):
    try:
        pdf_content = BytesIO(pdf_file.read())
        return extract_text(pdf_content)
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {e}")

def extract_form_fields_from_pdf(file):
    """
    Try to extract interactive form fields. If none are found,
    extract the text and use the LLM to determine which lines are questions.
    Returns a dictionary mapping question texts to their (initially empty) answers.
    """
    # Ensure we start reading from the beginning.
    file.seek(0)
    reader = PdfReader(file)
    fields = reader.get_fields()
    if fields:
        form_fields = {}
        for key, field in fields.items():
            # If a value exists, use it; otherwise, leave it empty.
            value = field.get("/V", "")
            form_fields[key] = value
        if form_fields:
            return form_fields

    # Fallback: extract text and ask the LLM to pick out questions.
    file.seek(0)
    text = extract_text_from_pdf(file)
    prompt = (
        "Extract only the questions from the following application form text. "
        "Assume that questions are lines starting with a pattern like 'Q1', 'Q2', etc. "
        "Return a JSON array containing just the question strings. Do not include any additional text. "
        f"Text: {text}"
    )
    messages = [{"role": "user", "content": prompt}]
    response = send_to_llm(messages)
    import json
    try:
        questions = json.loads(response)
        # Build a dictionary mapping each question to an empty answer.
        form_fields = {question: "" for question in questions}
    except Exception as e:
        # If the LLM output is not proper JSON, fall back to a regex approach.
        import re
        question_list = re.findall(r"(Q\d+\s*\|?\s*.*)", text)
        form_fields = {q.strip(): "" for q in question_list if q.strip()}
    return form_fields

import os
from datetime import datetime

def generate_qa_file(questions, answers):
    now = datetime.now()
    dt_string = now.strftime("%d.%m.%Y_%H_%M_%S")
    filename = f"qa_{dt_string}.txt"
    filepath = os.path.join("temp", filename)
    os.makedirs("temp", exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as file:
        for i, (question, answer) in enumerate(zip(questions, answers)):
            file.write(f"Q{i + 1}: {question}\nA{i + 1}: {answer}\n\n")

    return filepath
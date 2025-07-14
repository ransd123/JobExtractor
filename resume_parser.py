import os
import docx2txt
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    elif ext == ".pdf":
        try:
            reader = PdfReader(file_path)
            text = " ".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            print(f"PDF parsing error: {e}")
    elif ext == ".docx":
        try:
            text = docx2txt.process(file_path)
        except Exception as e:
            print(f"DOCX parsing error: {e}")
    return text

def extract_keywords(text, top_n=15):
    text = text.replace('\n', ' ').strip()
    if not text:
        return []

    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform([text])
    scores = zip(vectorizer.get_feature_names_out(), tfidf_matrix.toarray()[0])
    sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_scores[:top_n]]

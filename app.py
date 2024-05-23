import streamlit as st
import zipfile
import tempfile
import os
import requests
import base64
import json
from collections import Counter
from PyPDF2 import PdfReader
import docx
from streamlit_option_menu import option_menu
from nltk.tokenize import sent_tokenize, word_tokenize
from concurrent.futures import ThreadPoolExecutor, as_completed

# Check and download NLTK data
import nltk
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

img = get_img_as_base64("image.jpg")

page_bg_img = f"""
<style>
[data-testid="stSidebar"] > div:first-child {{
background-image: url("https://i.ibb.co/LzVCHgC/Untitled-desig.png");
background-position: left; 
background-repeat: no-repeat;
background-attachment: local;
}}

[data-testid="stHeader"] {{
background: rgba(0,0,0,0);
}}

[data-testid="stToolbar"] {{
right: 2rem;
}}
</style>
"""

st.markdown(page_bg_img, unsafe_allow_html=True)

def extract_all_files(zip_ref, temp_dir):
    files = []
    for root, _, filenames in os.walk(temp_dir):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files

def extract_zip(zip_file):
    try:
        with zipfile.ZipFile(zip_file, 'r', allowZip64=True) as zip_ref:
            temp_dir = tempfile.mkdtemp()
            zip_ref.extractall(temp_dir)
            files = extract_all_files(zip_ref, temp_dir)
            return files
    except zipfile.LargeZipFile:
        st.error('Error: File size is too large to open')

def extract_text(file):
    text = ""
    file_ext = os.path.splitext(file)[1].lower()
    if file_ext == ".docx":
        document = docx.Document(file)
        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"
    elif file_ext == ".txt":
        with open(file, "r", encoding="utf-8") as f:
            text = f.read()
    elif file_ext == ".pdf":
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def chunk_text(text, chunk_size=300):
    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = []
    current_chunk_word_count = 0
    
    for sentence in sentences:
        words = word_tokenize(sentence)
        sentence_word_count = len(words)
        
        if current_chunk_word_count + sentence_word_count <= chunk_size:
            current_chunk.append(sentence)
            current_chunk_word_count += sentence_word_count
        else:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_chunk_word_count = sentence_word_count
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def post_to_api(file, chunks, collection, doc_type):
    url = 'https://hanna-prodigy-ent-dev-backend-98b5967e61e5.herokuapp.com/add-master-object/file/'
    results = []
    for chunk in chunks:
        data = {
            'chunks': [chunk],
            'filename': os.path.basename(file),
            'collection': collection,
            'type': doc_type
        }
        response = requests.post(url, json=data)
        results.append((response.status_code, response.text))
    return results

def process_file(file, collection, doc_type):
    text = extract_text(file)
    chunks = chunk_text(text)
    return post_to_api(file, chunks, collection, doc_type)

def chat_with_model(query):
    api_url = "https://hanna-prodigy-ent-dev-backend-98b5967e61e5.herokuapp.com/chat/"
    payload = {
        "collection": "001",
        "query": query,
        "entity": "CMV",
        "user_id": "chay@gmial.com",
        "user": "chay",
        "language": "ENGLISH"
    }
    try:
        response = requests.post(api_url, data=json.dumps(payload), headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            response_text = response.text
            return response_text
        else:
            return f"Error: Received status code {response.status_code}\nResponse: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"

def main():
    with st.sidebar:
        choice = option_menu("MASTER VECTORS", ["Train MV", "Chat"], 
        icons=['upload','chat'], menu_icon="server", default_index=1, orientation="Vertical")
    if choice == "Train MV":
    

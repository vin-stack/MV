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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from streamlit_option_menu import option_menu
import pandas as pd
import sqlite3
from hashlib import sha256
import time

logs = []
chat_history = []

# Database setup
conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute('''
          CREATE TABLE IF NOT EXISTS users
          (username TEXT, password TEXT)
          ''')
conn.commit()

def hash_password(password):
    return sha256(password.encode()).hexdigest()

def add_user(username, password):
    c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hash_password(password)))
    conn.commit()

def authenticate_user(username, password):
    c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hash_password(password)))
    return c.fetchone() is not None

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
        return []

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
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    current_chunk = []
    current_word_count = 0
    for word in words:
        current_chunk.append(word)
        current_word_count += 1
        if current_word_count >= chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_word_count = 0
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks

def post_chunks_to_api(file, chunks, collection, doc_type):
    url = 'https://hanna-prodigy-ent-dev-backend-98b5967e61e5.herokuapp.com/add-master-object/file/'
    data = {
        'chunks': chunks,
        'filename': os.path.basename(file),
        'collection': collection,
        'type': doc_type
    }
    response = requests.post(url, json=data)
    return response.status_code, response.text

@st.cache_resource
def get_logs():
    return []

def add_log(log):
    logs = get_logs()
    logs.append(log)
    st.query_params.logs = logs

def process_file(file, collection, doc_type, chunk_size=300):
    text = extract_text(file)
    chunks = chunk_text(text, chunk_size)
    status_code, response_text = post_chunks_to_api(file, chunks, collection, doc_type)
    chunk_count = len(chunks)
    return status_code, response_text, chunk_count

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
    global logs
    global chat_history

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        with st.sidebar:
            choice = option_menu("MASTER VECTORS", ["Train MV", "Chat", "View Logs"], 
            icons=['upload','chat', 'list'], menu_icon="server", default_index=0, orientation="Vertical")
        if choice == "Train MV":
            zip_extractor(st.session_state.username)
        elif choice == "Chat":
            example()
        elif choice == "View Logs":
            view_logs()
    else:
        auth_page()

def auth_page():
    st.title("MASTER VECTORS")
    auth_mode = st.radio("Choose Authentication Mode", ["Login", "Register"])
    
    if auth_mode == "Login":
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if authenticate_user(username, password):
                st.success("Login successful")
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")

    elif auth_mode == "Register":
        st.subheader("Register")
        username = st.text_input("Choose a Username")
        password = st.text_input("Choose a Password", type="password")
        if st.button("Register"):
            if username and password:
                add_user(username, password)
                st.success("Registration successful. You can now login.")
            else:
                st.error("Please enter a valid username and password")

def zip_extractor(username):
    st.title("Zip File Extractor and Text Chunker")

    uploaded_file = st.file_uploader("Upload a zip file", type="zip")

    if uploaded_file is not None:
        extracted_files = extract_zip(uploaded_file)
        if extracted_files:
            st.write(f"Number of files extracted: {len(extracted_files)}")
            file_types = Counter([os.path.splitext(file)[1] for file in extracted_files])
            st.write("File types with counts:")
            for file_type, count in file_types.items():
                st.write(f"{file_type}: {count}")

            file_names = [os.path.basename(file) for file in extracted_files]
            selected_files = st.multiselect("Select files to train", ["All"] + file_names)
            if "All" in selected_files:
                selected_files = file_names

            collection = st.text_input("Enter Collection Name", value="MV001")
            st.caption("MV001 is the default one.")
            doc_type = st.text_input("Enter Type")
            
            if st.button("Train"):
                if collection and doc_type:
                    with st.spinner('🛠️ Training in progress...'):
                        to_process = [(file, collection, doc_type) for file in extracted_files if os.path.basename(file) in selected_files]

                        results = []
                        with ThreadPoolExecutor() as executor:
                            futures = {executor.submit(process_file, file, collection, doc_type): file for file, collection, doc_type in to_process}
                            for future in as_completed(futures):
                                try:
                                    result = future.result()
                                    results.append((futures[future], result))
                                except Exception as e:
                                    st.error(f"Error processing file: {e}")

                        for file, (status_code, response_text, chunk_count) in results:
                            filename = os.path.basename(file)
                            st.success(f"Status: {filename}, {status_code}, Response: {response_text}, Chunks: {chunk_count}")
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            log_entry = {
                                "filename": filename,
                                "collection": collection,
                                "type": doc_type,
                                "username": username,
                                "status_code": status_code,
                                "chunk_count": chunk_count,
                                "message": response_text,
                                "timestamp": timestamp
                            }
                            add_log(log_entry)
                else:
                    st.error("Please enter both collection name and type.")

def example():
    global chat_history

    query = st.text_input("Enter your query:")

    if st.button("ASK HANNA->"):
        with st.spinner('🤔 Hanna is thinking...'):
            response = chat_with_model(query)
            chat_history.append({"role": "assistant", "content": response})
            chat_history.append({"role": "user", "content": query})

    for message in reversed(chat_history):
        if message["role"] == "assistant":
            st.write(f"**🤖 Hanna:** {message['content']}")
            st.markdown("----------------")
        elif message["role"] == "user":
            st.write(f"**👧🏻 User:** {message['content']}")

def view_logs():
    logs = get_logs()
    st.title("View Logs")
    st.caption("Select the files that you want to undo the training.")

    if logs:
        df_logs = pd.DataFrame(logs)
        df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp'])
        df_logs.sort_values(by='timestamp', ascending=False, inplace=True)
        
        def delete_logs(indices):
            indices_to_drop = [idx for idx in indices if idx < len(logs)]
            indices_to_drop.sort(reverse=True)
            for idx in indices_to_drop:
                log_entry = logs[idx]
                if log_entry["username"] == st.session_state.username:
                    collection = log_entry["collection"]
                    message = log_entry["message"]
                    kl(collection, message)
                    del logs[idx]
                else:
                    st.error("Restricted: You can only delete your own logs.")
                    time.sleep(10)
            st.query_params.logs = logs
            st.rerun()

        def kl(collection, message):
            parsed_data = json.loads(message)
            result = parsed_data["msg"]
            url = 'https://hanna-prodigy-ent-dev-backend-98b5967e61e5.herokuapp.com/remove-master-objects/uuid/'
            data = {
                'collection': collection,
                'uuid': result
            }
            response = requests.post(url, json=data)
            return response

        def dataframe_with_selections(df_logs):
            df_with_selections = df_logs.copy()
            df_with_selections.insert(0, "Delete", False)
            edited_df = st.data_editor(
                df_with_selections,
                hide_index=True,
                column_config={"Delete": st.column_config.CheckboxColumn(required=True)},
                disabled=df_logs.columns,
            )

            selected_rows = edited_df[edited_df.Delete]
            return selected_rows.drop('Delete', axis=1)

        selection = dataframe_with_selections(df_logs)
        st.write("Files to Delete:")
        st.write(selection)

        if st.button("Delete"):
            indices = selection.index.tolist()
            delete_logs(indices)
            st.success("Files removed successfully.")
            time.sleep(10)
            
    else:
        st.write("No logs to display.")

if __name__ == '__main__':
    main()

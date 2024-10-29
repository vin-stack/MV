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
import time
from llama_index.core.node_parser import SentenceSplitter

logs = []
chat_history = []

# URL options
URL_OPTIONS = {
    "Production": "https://hanna-prodigy-ent-dev-backend-98b5967e61e5.herokuapp.com",
    "Staging": "https://hanna-prodigy-staging-backend.herokuapp.com",
    "Development": "https://hanna-prodigy-dev-backend.herokuapp.com"
}

def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

img = get_img_as_base64("image.jpg")

page_bg_img = f"""
<style>
[data-testid="stSidebar"] > div:first-child {{
background-image: url("https://i.ibb.co/RN5yJCc/Untitled-desig.png");
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
    splitter = SentenceSplitter(chunk_size=chunk_size)  # Initialize the splitter
    chunks = splitter.split_text(text)  # Use the correct method to split text, if available
    return chunks

def post_chunks_to_api(file, chunks, collection, doc_type, base_url):
    url = f"{base_url}/add-master-object/file/"
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

def process_file(file, collection, doc_type, base_url, chunk_size=300):
    text = extract_text(file)
    chunks = chunk_text(text, chunk_size)
    status_code, response_text = post_chunks_to_api(file, chunks, collection, doc_type, base_url)
    chunk_count = len(chunks)
    return status_code, response_text, chunk_count

def process_large_file_in_batches(file, collection, doc_type, base_url, chunk_size=300, batch_size=150, delay=10):
    text = extract_text(file)
    chunks = chunk_text(text, chunk_size)
    
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i+batch_size]
        status_code, response_text = post_chunks_to_api(file, batch_chunks, collection, doc_type, base_url)
        time.sleep(delay)
    
    chunk_count = len(chunks)
    return status_code, response_text, chunk_count

def chat_with_model(query, base_url):
    api_url = f"{base_url}/chat/"
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

    st.sidebar.title("Configuration")
    selected_url = st.sidebar.selectbox("Select API Base URL", list(URL_OPTIONS.keys()))
    base_url = URL_OPTIONS[selected_url]

    with st.sidebar:
        choice = option_menu("MASTER VECTORS", ["Train MV", "Chat", "View Logs"], 
        icons=['upload','chat', 'list'], menu_icon="server", default_index=0, orientation="Vertical")
    if choice == "Train MV":
        zip_extractor(base_url)
    elif choice == "Chat":
        example(base_url)
    elif choice == "View Logs":
        view_logs()

def zip_extractor(base_url):
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

                        small_files = []
                        queue1 = []
                        queue2 = []

                        for file, collection, doc_type in to_process:
                            text_length = len(extract_text(file))
                            if text_length < 5000:
                                small_files.append((file, collection, doc_type))
                            elif 5000 <= text_length < 10000:
                                queue1.append((file, collection, doc_type))
                            else:
                                queue2.append((file, collection, doc_type))

                        results = []

                        with ThreadPoolExecutor() as executor:
                            # Process small files first
                            futures = {executor.submit(process_file, file, collection, doc_type, base_url): file for file, collection, doc_type in small_files}
                            for future in as_completed(futures):
                                try:
                                    result = future.result()
                                    results.append((futures[future], result))
                                except Exception as e:
                                    st.error(f"Error processing file: {e}")

                            # Process queue1 files
                            for file, collection, doc_type in queue1:
                                result = process_large_file_in_batches(file, collection, doc_type, base_url)
                                results.append((file, result))

                            # Process queue2 files
                            for file, collection, doc_type in queue2:
                                result = process_large_file_in_batches(file, collection, doc_type, base_url)
                                results.append((file, result))

                        for file, (status_code, response_text, chunk_count) in results:
                            filename = os.path.basename(file)
                            st.success(f"Status: {filename}, {status_code}, Response: {response_text}, objects added: {chunk_count}")
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            log_entry = {
                                "filename": filename,
                                "collection": collection,
                                "type": doc_type,
                                "status_code": status_code,
                                "objects added": chunk_count,
                                "message": response_text,
                                "timestamp": timestamp
                            }
                            add_log(log_entry)
                else:
                    st.error("Please enter both collection name and type.")

def example(base_url):
    global chat_history

    query = st.text_input("Enter your query:")

    if st.button("ASK HANNA->"):
        with st.spinner('🤔 Hanna is thinking...'):
            response = chat_with_model(query, base_url)
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
                collection = log_entry["collection"]
                message = log_entry["message"]
                kl(collection, message)
                del logs[idx]
                st.success("Files removed successfully.")
            st.query_params.logs = logs
            st.rerun()

        def kl(collection, message):
            parsed_data = json.loads(message)
            result = parsed_data["msg"]
            url = f"{URL_OPTIONS['Production']}/remove-master-objects/uuid/"
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
            
    else:
        st.write("No logs to display.")

if __name__ == '__main__':
    main()

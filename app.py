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
import time

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

def post_to_api(file, chunks, collection, doc_type):
    url = 'https://hanna-prodigy-ent-dev-backend-98b5967e61e5.herokuapp.com/add-master-object/file/'
    data = {
        'chunks': chunks,
        'filename': os.path.basename(file),
        'collection': collection,
        'type': doc_type
    }
    response = requests.post(url, json=data)
    return response.status_code, response.text

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
                             icons=['upload', 'chat'], menu_icon="server", default_index=1, orientation="Vertical")
    if choice == "Train MV":
        zip_extractor()
    elif choice == "Chat":
        example()

def zip_extractor():
    st.title("Zip File Extractor and Text Chunker")

    uploaded_file = st.file_uploader("Upload a zip file", type="zip")

    if uploaded_file is not None:
        if 'processed_files' not in st.session_state:
            st.session_state.processed_files = 0
        if 'extracted_files' not in st.session_state:
            extracted_files = extract_zip(uploaded_file)
            st.session_state.extracted_files = extracted_files
        else:
            extracted_files = st.session_state.extracted_files

        if extracted_files:
            st.write(f"Number of files extracted: {len(extracted_files)}")
            file_types = Counter([os.path.splitext(file)[1] for file in extracted_files])
            st.write("File types with counts:")
            for file_type, count in file_types.items():
                st.write(f"{file_type}: {count}")

            # Use a multiselect widget for file selection
            file_names = [os.path.basename(file) for file in extracted_files]
            selected_files = st.multiselect("Select files to train", ["All"] + file_names, default="All")
            if "All" in selected_files:
                selected_files = file_names

            # Get user input for collection and type
            collection = st.text_input("Enter Collection Name")
            st.caption("MV001 is the default one.")
            doc_type = st.text_input("Enter Type")

            def process_files(collection, doc_type):
                if collection and doc_type:
                    with st.spinner('🛠️Training in progress...'):
                        start_index = st.session_state.processed_files
                        end_index = min(start_index + 10, len(selected_files))
                        to_process = [(extracted_files[i], extract_text(extracted_files[i]), collection, doc_type) for i in range(start_index, end_index)]

                        results = []
                        for file, text, collection, doc_type in to_process:
                            status_code, response_text = post_to_api(file, [text], collection, doc_type)
                            results.append((status_code, response_text))

                        # Update processed files count
                        st.session_state.processed_files = end_index

                        # Display results
                        for status_code, response_text in results:
                            st.write(f"Status: {status_code}, Response: {response_text}")
                            st.success(f"Status: {status_code}, Response: {response_text}", icon="✅")

                        if end_index < len(selected_files):
                            st.info("Waiting to process the next batch...")
                            # Add a delay of 10 seconds
                            time.sleep(40)
                            process_files(collection, doc_type)
                        else:
                            st.success("All files processed!", icon="✅")
                else:
                    st.error("Please enter both collection name and type.")

            if st.button("Train"):
                process_files(collection, doc_type)

def example():
    chat_history = st.session_state.get('chat_history', [])

    query = st.text_input("Enter your query:")

    if st.button("ASK HANNA->"):
        with st.spinner('🤔Hanna is thinking...'):
            response = chat_with_model(query)
            chat_history.append({"role": "assistant", "content": response})
            chat_history.append({"role": "user", "content": query})

            st.session_state['chat_history'] = chat_history

    for message in reversed(chat_history):
        if message["role"] == "assistant":
            st.write(f"**🤖Hanna:** {message['content']}")
            st.markdown("----------------")
        elif message["role"] == "user":
            st.write(f"**👧🏻User:** {message['content']}")

if __name__ == '__main__':
    main()

import streamlit as st
import zipfile
import tempfile
import os
import requests
import json
from collections import Counter
from PyPDF2 import PdfReader
import docx
from streamlit_option_menu import  option_menu
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
    url = 'https://new-weaviate-chay-ce16dcbef0d9.herokuapp.com/add-master-object/file/'
    data = {
        'chunks': chunks,
        'filename': os.path.basename(file),
        'collection': collection,
        'type': doc_type
    }
    response = requests.post(url, json=data)
    return response.status_code, response.text

def chat_with_model(query):
    api_url = "https://new-weaviate-chay-ce16dcbef0d9.herokuapp.com/chat/"
    payload = {
        "collection": "MV001",
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
    		choice = option_menu("MASTER VECTORS", ["Train MV","Chat"], 
        	icons=['upload','chat'], menu_icon="server", default_index=1,orientation="Vertical")
    if choice == "Zip Extractor":
        zip_extractor()
    elif choice == "Chat":
        example()
   
    	
	


def zip_extractor():
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

            # Use a multiselect widget for file selection
            file_names = [os.path.basename(file) for file in extracted_files]
            selected_files = st.multiselect("Select files to train", ["All"] + file_names)
            if "All" in selected_files:
                selected_files = file_names

            # Get user input for collection and type
            collection = st.text_input("Enter Collection Name")
            doc_type = st.text_input("Enter Type")
            
            if st.button("Train"):
                if collection and doc_type:
                    # Filter selected files
                    to_process = [(file, extract_text(file), collection, doc_type) for file in extracted_files if os.path.basename(file) in selected_files]

                    results = []
                    for file, text, collection, doc_type in to_process:
                        status_code, response_text = post_to_api(file, [text], collection, doc_type)
                        results.append((status_code, response_text))
                    
                    # Display results
                    for status_code, response_text in results:
                        st.write(f"Status: {status_code}, Response: {response_text}")
                else:
                    st.error("Please enter both collection name and type.")
            
           

def example():
    chat_history = st.session_state.get('chat_history', [])

    query = st.text_input("Enter your query:")

    if query:
        response = chat_with_model(query)
        chat_history.append({"role": "assistant", "content": response})
        chat_history.append({"role": "user", "content": query})
        
        st.session_state['chat_history'] = chat_history

    for message in reversed(chat_history):
        if message["role"] == "assistant":
            
            st.write(f"**🤖Assistant:** {message['content']}")
            st.markdown("----------------")
        elif message["role"] == "user":
            
            st.write(f"**👧🏻User:** {message['content']}")

if __name__ == '__main__':
    main()

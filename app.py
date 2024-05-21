import streamlit as st
import zipfile
import tempfile
import os
import requests
import re
from collections import Counter
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import docx
import io
import json

class ChunkText:
    def __init__(self, size: int = 1300):
        self.__rcts = RecursiveCharacterTextSplitter(chunk_overlap=0, chunk_size=size, length_function=len)

    def chunk_text(self, text: str):
        split_text = self.__rcts.split_text(text)
        return split_text

def process_file(file):
    # Extract text and chunk it
    text = extract_text(file)
    return text

def extract_text(file):
    # Extract text from various file formats
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

def extract_zip(zip_file):
    text_data = []
    try:
        with zipfile.ZipFile(zip_file, 'r', allowZip64=True) as zip_ref:
            temp_dir = tempfile.mkdtemp()
            zip_ref.extractall(temp_dir)
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    text = process_file(file_path)
                    text_data.append((file, text))
        return text_data
    except zipfile.LargeZipFile:
        st.error('Error: File size is too large to open')

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
api_url="https://new-weaviate-chay-ce16dcbef0d9.herokuapp.com/chat/"
def chat_with_model(query):
    # Define the request payload
    payload = {
        "collection": "MV001",
        "query": query,
        "entity": "CMV",
        "user_id": "chay@gmial.com",
        "user": "chay",
        "language": "ENGLISH"
    }

    try:
        # Send the POST request
        response = requests.post(api_url, data=json.dumps(payload), headers={"Content-Type": "application/json"})

        # Check if the request was successful
        if response.status_code == 200:
            # If the response is a streaming response, handle it accordingly
            response_text = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    response_text += decoded_line + "\n"
            return response_text
        else:
            return f"Error: Received status code {response.status_code}\nResponse: {response.text}"

    except requests.exceptions.RequestException as e:
        return f"Error: {e}"


def main():
    st.title("Zip File Extractor and Text Chunker")

    uploaded_file = st.file_uploader("Upload a zip file", type="zip")
    
    if uploaded_file is not None:
        text_data = extract_zip(uploaded_file)

        if text_data:
            st.write("Text Data:")
            file_names = []
            for file, text in text_data:
                file_basename = os.path.basename(file)
                file_names.append(file_basename)
                with st.expander(f"Text from {file_basename}"):
                    st.write(text)

            # Use a multiselect widget for file selection
            selected_files = st.multiselect("Select files to train", ["All"] +file_names)
            if "All" in selected_files:
                selected_files = file_names

            # Get user input for collection and type
            collection = st.text_input("Enter Collection Name")
            doc_type = st.text_input("Enter Type")
            
            if st.button("Train"):
                if collection and doc_type:
                    # Filter selected files
                    to_process = [(file, text, collection, doc_type) for file, text in text_data if os.path.basename(file) in selected_files]

                    results = []
                    for file, text, collection, doc_type in to_process:
                        chunked_text = chunk_text(text)
                        status_code, response_text = post_to_api(file, chunked_text, collection, doc_type)
                        results.append((status_code, response_text))
                    
                    # Display results
                    for status_code, response_text in results:
                        st.write(f"Status: {status_code}, Response: {response_text}")
                else:
                    st.error("Please enter both collection name and type.")
                    
            query = st.text_input("Enter your query:")

            # Button to submit the query
            if st.button("Submit"):
                if query:
                    # Get the response from the model
                    response = chat_with_model(query)
                    # Display the response in the Streamlit app
                    st.write(response)
                    st.text_area("Response from the Model:", response, height=300)
                else:
                    st.warning("Please enter a query.")

def chunk_text(text: str):
    # Initialize the RecursiveCharacterTextSplitter with chunk size 300
    rcts = RecursiveCharacterTextSplitter(chunk_overlap=0, chunk_size=300, length_function=len)
    # Split the text into chunks
    chunked_text = rcts.split_text(text)
    return chunked_text

if __name__ == '__main__':
    main()

import streamlit as st
import zipfile
import tempfile
import os
import requests
import pandas as pd
from collections import Counter
import re
from streamlit_extras.dataframe_explorer import dataframe_explorer

def process_file(file):
    # Extract text and chunk it in 300 words
    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
        words = re.findall(r'\w+', text)
        chunks = [' '.join(words[i:i+300]) for i in range(0, len(words), 300)]
        
        # Return chunks with file name for display
        return file, chunks

def extract_all_files(zip_ref, temp_dir):
    zip_ref.extractall(temp_dir)
    all_files = []
    for root, _, files in os.walk(temp_dir):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

def extract_zip(zip_file):
    chunks_data = []
    try:
        with zipfile.ZipFile(zip_file, 'r', allowZip64=True) as zip_ref:
            # Create a temporary directory to extract files
            temp_dir = tempfile.mkdtemp()
            
            # Extract all files and handle nested directories
            files = extract_all_files(zip_ref, temp_dir)
            
            # Display number of files
            st.write(f"Number of files extracted: {len(files)}")
            
            # Count file types
            file_types = Counter([os.path.splitext(file)[1] for file in files])
            st.write("File types with counts:")
            for file_type, count in file_types.items():
                st.write(f"{file_type}: {count}")

            # Process files without multiprocessing
            for file in files:
                file, chunks = process_file(file)
                chunks_data.append((file, chunks))
                st.success(f"Processed {file}")

    except zipfile.LargeZipFile:
        st.error('Error: File size is too large to open')
    return chunks_data

def post_to_api(file, chunks, collection, doc_type):
    url = 'https://new-weaviate-chay-ce16dcbef0d9.herokuapp.com/add-master-object/file/'
    data = {
        'document': chunks,
        'filename': os.path.basename(file),
        'collection': collection,
        'type': doc_type
    }
    response = requests.post(url, json=data)
    return response.status_code, response.text

def main():
    st.title("Zip File Extractor and Text Chunker")

    uploaded_file = st.file_uploader("Upload a zip file", type="zip")
    
    if uploaded_file is not None:
        chunks_data = extract_zip(uploaded_file)

        if chunks_data:
            st.write("Chunks Data:")
            # Create a table to display file info and allow user to select files
            table_data = []
            for file, chunks in chunks_data:
                file_basename = os.path.basename(file)
                table_data.append({'Select': False, 'Filename': file_basename, 'Chunks': len(chunks)})
            
            df = pd.DataFrame(table_data)

            # Use the streamlit-extras dataframe explorer for interactive table
            edited_df = dataframe_explorer(df)

            # Get user input for collection and type
            collection = st.text_input("Enter Collection Name")
            doc_type = st.text_input("Enter Type")
            
            if st.button("Train"):
                if collection and doc_type:
                    # Filter selected files
                    to_process = [(row['Filename'], next(chunks for file, chunks in chunks_data if os.path.basename(file) == row['Filename']), collection, doc_type) for _, row in edited_df.iterrows() if row['Select']]

                    results = []
                    for file, chunks, collection, doc_type in to_process:
                        status_code, response_text = post_to_api(file, chunks, collection, doc_type)
                        results.append((status_code, response_text))
                    
                    # Display results
                    for status_code, response_text in results:
                        st.write(f"Status: {status_code}, Response: {response_text}")
                else:
                    st.error("Please enter both collection name and type.")

if __name__ == '__main__':
    main()

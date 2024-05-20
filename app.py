import streamlit as st
import zipfile
import tempfile
import os
import multiprocessing
from collections import Counter
import re

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

            # Ask for permission to extract text and chunk it
            if st.checkbox("Do you want to extract text and chunk it?"):
                # Use multiprocessing to handle extraction and chunking in parallel
                with st.spinner('Processing files...'):
                    pool = multiprocessing.Pool()
                    results = pool.map(process_file, files)
                    pool.close()
                    pool.join()

                # Collect results
                for file, chunks in results:
                    chunks_data.append((file, chunks))
                    st.success(f"Processed {file}")

                return chunks_data
    except zipfile.LargeZipFile:
        st.error('Error: File size is too large to open')
    return chunks_data

def main():
    st.title("Zip File Extractor and Text Chunker")

    uploaded_file = st.file_uploader("Upload a zip file", type="zip",max_upload_size=10000*1024*1024)
    
    if uploaded_file is not None:
        chunks_data = extract_zip(uploaded_file)

        if chunks_data:
            st.write("Chunks Data:")
            for file, chunks in chunks_data:
                with st.expander(f"Chunks from {os.path.basename(file)}"):
                    for i, chunk in enumerate(chunks):
                        st.write(f"Chunk {i+1}:")
                        st.write(chunk[:300])  # Display the first 300 characters of each chunk

if __name__ == '__main__':
    main()

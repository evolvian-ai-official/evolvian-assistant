# api/modules/assistant_rag/document_utils.py

import os
import xml.etree.ElementTree as ET
import zipfile
from typing import List
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def load_document(file_path: str) -> List[Document]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".docx":
        with zipfile.ZipFile(file_path) as archive:
            raw_xml = archive.read("word/document.xml")
        root = ET.fromstring(raw_xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            runs = [
                node.text.strip()
                for node in paragraph.findall(".//w:t", namespace)
                if node.text and node.text.strip()
            ]
            if runs:
                paragraphs.append(" ".join(runs))
        return [Document(page_content="\n".join(paragraphs).strip(), metadata={"source": file_path})]
    elif ext == ".txt":
        loader = TextLoader(file_path)
    else:
        raise ValueError(f"Formato de archivo no soportado: {ext}")
    return loader.load()


def chunk_documents(docs: List[Document], chunk_size: int = 800, chunk_overlap: int = 100) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return splitter.split_documents(docs)

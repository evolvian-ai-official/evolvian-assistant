import os
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import OpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from modules.assistant_rag.supabase_client import save_history, supabase

DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."

def load_document(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path)
    else:
        raise ValueError(f"Formato de archivo no soportado: {ext}")
    return loader.load()

def chunk_documents(documents: List[str]):
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    return splitter.split_documents(documents)

def embed_and_store(docs, client_id: str):
    persist_directory = f"data/chroma_store_{client_id}"
    os.makedirs(persist_directory, exist_ok=True)
    embeddings = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    vectordb.persist()
    return vectordb

def load_vectorstore(client_id: str):
    persist_directory = f"data/chroma_store_{client_id}"
    embeddings = OpenAIEmbeddings()
    vectordb = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    return vectordb

def get_prompt_for_client(client_id: str) -> str:
    try:
        res = supabase.table("client_settings").select("custom_prompt").eq("client_id", client_id).single().execute()
        return res.data["custom_prompt"] if res.data and res.data.get("custom_prompt") else DEFAULT_PROMPT
    except Exception as e:
        print(f"⚠️ No se pudo obtener el custom_prompt. Usando default. Error: {e}")
        return DEFAULT_PROMPT

def ask_question(question: str, client_id: str):
    prompt = get_prompt_for_client(client_id)
    vectordb = load_vectorstore(client_id)

    qa_chain = RetrievalQA.from_chain_type(
        llm=OpenAI(),
        retriever=vectordb.as_retriever(),
        return_source_documents=True,
        chain_type_kwargs={
            "prompt": PromptTemplate(
                template=f"{prompt}\n\nContexto:\n{{context}}\n\nPregunta:\n{{question}}",
                input_variables=["context", "question"]
            )
        }
    )

    result = qa_chain(question)
    answer = result['result']

    print(f"✅ Guardando pregunta de {client_id}: {question}")
    print(f"📛 client_id usado en pregunta: {client_id}")
    save_history(client_id, question, answer)

    return answer

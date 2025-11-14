"""
Document Chunking Utilities
Split documents into smaller chunks for better retrieval
"""

from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

def split_documents_to_chunks(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Document]:
    """
    Chia documents thành các chunks nhỏ hơn
    
    Args:
        documents: List of LangChain Document objects
        chunk_size: Kích thước mỗi chunk (characters)
        chunk_overlap: Overlap giữa các chunks
        
    Returns:
        List of chunked Document objects
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Đã chia {len(documents)} documents thành {len(chunks)} chunks")
    
    return chunks

def split_text_to_chunks(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Chia text thành các chunks nhỏ hơn
    
    Args:
        text: Text string to split
        chunk_size: Kích thước mỗi chunk (characters)
        chunk_overlap: Overlap giữa các chunks
        
    Returns:
        List of text chunks
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    print(f"✅ Đã chia text thành {len(chunks)} chunks")
    
    return chunks

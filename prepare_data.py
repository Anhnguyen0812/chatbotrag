# File: prepare_bm25_data.py

import os
import pickle
from langchain_community.document_loaders import CSVLoader
from langchain_core.documents import Document

# --- Cấu hình ---
DATA_FILE = 'dulieu.csv'
HANOI_FILE = 'Hanoi.md'
DOCUMENTS_PICKLE_FILE = "bm25_documents.pkl" # File sẽ lưu trữ các documents

# --- 1. Tải và xử lý dữ liệu từ CSV ---
print("--- BẮT ĐẦU CHUẨN BỊ DỮ LIỆU BM25 ---")
print(f"1. Đang tải dữ liệu từ {DATA_FILE}...")
loader = CSVLoader(file_path=DATA_FILE, encoding='utf-8')
documents = loader.load()
print(f"-> Đã tải {len(documents)} documents từ CSV.")

# --- 2. Tải dữ liệu từ Hanoi.md ---
print(f"2. Đang tải dữ liệu từ {HANOI_FILE}...")
if os.path.exists(HANOI_FILE):
    with open(HANOI_FILE, 'r', encoding='utf-8') as f:
        hanoi_content = f.read()
    
    # Tách theo đoạn văn (mỗi đoạn là 1 document)
    hanoi_chunks = [chunk.strip() for chunk in hanoi_content.split('\n\n') if chunk.strip()]
    hanoi_docs = [Document(page_content=chunk, metadata={"source": "Hanoi.md"}) for chunk in hanoi_chunks]
    documents.extend(hanoi_docs)
    print(f"-> Đã tải thêm {len(hanoi_docs)} documents từ Hanoi.md.")
else:
    print(f"-> Không tìm thấy file {HANOI_FILE}, bỏ qua.")

print(f"-> Tổng cộng: {len(documents)} documents.")

# (Tùy chọn) Nếu bạn muốn dùng PyViTokenizer để tách từ tiếng Việt cho BM25:
# from pyvi import ViTokenizer
# for doc in documents:
#     doc.page_content = ViTokenizer.tokenize(doc.page_content)
# print("-> Đã Tokenize tiếng Việt (nếu bật).")


# --- 3. Lưu trữ Documents xuống đĩa ---
print(f"3. Đang lưu trữ Documents vào file '{DOCUMENTS_PICKLE_FILE}'...")
with open(DOCUMENTS_PICKLE_FILE, 'wb') as f:
    pickle.dump(documents, f)

print("--- HOÀN THÀNH CHUẨN BỊ DỮ LIỆU ---")
print(f"Documents đã được lưu thành công tại file: {DOCUMENTS_PICKLE_FILE}")
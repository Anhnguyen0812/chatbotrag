# File: prepare_bm25_data.py

import os
import pickle
from langchain_community.document_loaders import CSVLoader

# --- Cấu hình ---
DATA_FILE = 'dulieu.csv'
DOCUMENTS_PICKLE_FILE = "bm25_documents.pkl" # File sẽ lưu trữ các documents

# --- 1. Tải và xử lý dữ liệu (Chunking) ---
print("--- BẮT ĐẦU CHUẨN BỊ DỮ LIỆU BM25 ---")
print(f"1. Đang tải và chia nhỏ dữ liệu từ {DATA_FILE}...")
loader = CSVLoader(file_path=DATA_FILE, encoding='utf-8')
documents = loader.load()
print(f"-> Đã tải {len(documents)} documents.")

# (Tùy chọn) Nếu bạn muốn dùng PyViTokenizer để tách từ tiếng Việt cho BM25:
# from pyvi import ViTokenizer
# for doc in documents:
#     doc.page_content = ViTokenizer.tokenize(doc.page_content)
# print("-> Đã Tokenize tiếng Việt (nếu bật).")


# --- 2. Lưu trữ Documents xuống đĩa ---
print(f"2. Đang lưu trữ Documents vào file '{DOCUMENTS_PICKLE_FILE}'...")
with open(DOCUMENTS_PICKLE_FILE, 'wb') as f:
    pickle.dump(documents, f)

print("--- HOÀN THÀNH CHUẨN BỊ DỮ LIỆU ---")
print(f"Documents đã được lưu thành công tại file: {DOCUMENTS_PICKLE_FILE}")
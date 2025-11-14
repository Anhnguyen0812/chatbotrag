import os
import csv
from pathlib import Path

# Đường dẫn đến thư mục notes và file CSV
notes_folder = Path("notes")
csv_file = Path("dulieu.csv")

# Đọc tất cả các file txt trong thư mục notes
notes_data = []

for txt_file in notes_folder.glob("*.txt"):
    with open(txt_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Thêm metadata về nguồn
        file_name = txt_file.stem
        
        # Phân loại dữ liệu dựa trên tên file
        if 'gift' in file_name:
            loai = "qua_tang"
            ten = f"Gợi ý quà tặng từ {file_name}"
        elif 'plan' in file_name:
            loai = "ke_hoach_hen_ho"
            ten = f"Kế hoạch hẹn hò từ {file_name}"
        else:
            loai = "khac"
            ten = f"Dữ liệu từ {file_name}"
        
        # Thêm dòng mới vào danh sách
        notes_data.append({
            'loai': loai,
            'ten': ten,
            'tinh_thanh_hoac_thuong_hieu': f"Nguồn: {file_name}",
            'mota_chi_tiet': content.replace('\n', ' ').replace('"', '""'),
            'doi_tuong': 'tất cả',
            'so_thich_hoac_dip_le': 'đa dạng',
            'chi_phi_hoac_muc_gia': 'đa dạng',
            'hoat_dong_noi_bat': f'Thông tin chi tiết từ {file_name}'
        })

# Đọc dữ liệu hiện có từ CSV
existing_data = []
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing_data = list(reader)

# Ghi lại toàn bộ dữ liệu (cũ + mới) vào CSV
with open(csv_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    
    # Ghi dữ liệu cũ
    writer.writerows(existing_data)
    
    # Ghi dữ liệu mới
    writer.writerows(notes_data)

print(f"✅ Đã thêm {len(notes_data)} dòng dữ liệu mới từ thư mục notes vào file dulieu.csv")
print(f"📊 Tổng số dòng dữ liệu hiện tại: {len(existing_data) + len(notes_data)}")

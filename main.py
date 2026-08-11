import os
import requests

# 1. Kiểm tra biến môi trường
cookie_str = os.getenv("MY_COOKIE")
sheet_url = os.getenv("SHEET_URL")

print("--- KIỂM TRA BIẾN MÔI TRƯỜNG ---")
print(f"Cấu hình MY_COOKIE: {'ĐÃ CÓ' if cookie_str else 'CHƯA CÓ (THIẾU)'}")
print(f"Cấu hình SHEET_URL: {'ĐÃ CÓ' if sheet_url else 'CHƯA CÓ (THIẾU)'}")

if not cookie_str or not sheet_url:
    print("❌ Dừng chạy do thiếu biến môi trường trong GitHub Secrets!")
    exit(1)

# 2. Gửi request lấy dữ liệu
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": cookie_str
}

target_url = "https://httpbin.org/cookies"

try:
    print("\n--- 1. BẮT ĐẦU GỬI REQUEST LẤY DỮ LIỆU ---")
    res = requests.get(target_url, headers=headers, timeout=10)
    print(f"Mã phản hồi từ web mục tiêu: {res.status_code}")
    
    payload = {
        "status": f"Mã HTTP {res.status_code}",
        "result": res.text[:500]
    }
    
    print("\n--- 2. BẮT ĐẦU GỬI DỮ LIỆU SANG GOOGLE SHEET ---")
    sheet_res = requests.post(sheet_url, json=payload, timeout=15)
    
    print(f"Mã phản hồi từ Google Sheet: {sheet_res.status_code}")
    print(f"Nội dung phản hồi từ Google Sheet: {sheet_res.text}")

except Exception as e:
    print(f"❌ Có lỗi ngoại lệ xảy ra: {e}")

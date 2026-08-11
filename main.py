import os
import requests

# 1. Lấy Cookie và Sheet URL từ GitHub Secrets
cookie_str = os.getenv("MY_COOKIE")
sheet_url = os.getenv("SHEET_URL")

if not cookie_str or not sheet_url:
    print("❌ Lỗi: Chưa cấu hình MY_COOKIE hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

# 2. Cấu hình Headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": cookie_str
}

# 3. URL trang web cần lấy dữ liệu
target_url = "https://httpbin.org/cookies"

try:
    print("Đang lấy dữ liệu từ trang web...")
    response = requests.get(target_url, headers=headers, timeout=10)
    
    status_text = f"Mã {response.status_code}"
    result_text = response.text[:1000] # Lấy 1000 ký tự kết quả
    
    # 4. Gửi kết quả trực tiếp sang Google Trang tính
    print("Đang gửi kết quả sang Google Trang tính...")
    payload = {
        "status": status_text,
        "result": result_text
    }
    
    sheet_response = requests.post(sheet_url, json=payload)
    print(f"Kết quả lưu vào Sheet: {sheet_response.text}")

except Exception as e:
    print(f"❌ Có lỗi xảy ra: {e}")

import os
import requests

sheet_url = os.getenv("SHEET_URL")

print("==========================================")
print("       TEST CHẨN ĐOÁN GOOGLE SHEET        ")
print("==========================================")

# 1. Kiểm tra xem SHEET_URL có bị trống không
if not sheet_url:
    print("❌ LỖI 1: Biến SHEET_URL trong GitHub Secrets đang bị Trống!")
    exit(1)

print(f"👉 Link SHEET_URL hiện tại: {sheet_url[:35]}...{sheet_url[-10:] if len(sheet_url) > 10 else ''}")

# 2. Kiểm tra định dạng link
if "docs.google.com/spreadsheets" in sheet_url:
    print("❌ LỖI 2: Bạn đang dán LINK TRANG GOOGLE SHEET (docs.google.com)! Bắt buộc phải dán Link Web App (script.google.com).")
    exit(1)

if not sheet_url.startswith("https://script.google.com/macros/s/"):
    print("❌ LỖI 3: Link SHEET_URL sai cấu trúc Web App! (Link chuẩn phải bắt đầu bằng https://script.google.com/macros/s/).")
    exit(1)

# 3. Gửi Request thử nghiệm trực tiếp sang Google Sheet
print("\n🔄 Đang thử gửi 1 dòng test dữ liệu sang Google Sheet...")
test_payload = {
    "status": "TEST CHẨN ĐOÁN TỪ GITHUB",
    "result": "Nếu bạn thấy dòng này trên Google Sheet tức là hệ thống đã THÀNH CÔNG 100%!"
}

try:
    res = requests.post(sheet_url, json=test_payload, timeout=20)
    print(f"Mã phản hồi HTTP: {res.status_code}")
    print(f"Nội dung Google Sheet trả về: {res.text}")
    
    if "SUCCESS_OK" in res.text or "OK" in res.text:
        print("\n✅ THÀNH CÔNG 100%! Hãy mở Google Trang tính kiểm tra Hàng số 2 ngay bây giờ.")
    else:
        print("\n❌ THẤT BẠI: Google Sheet trả về trang lỗi!")
except Exception as e:
    print(f"\n❌ LỖI NGOẠI LỆ: {e}")

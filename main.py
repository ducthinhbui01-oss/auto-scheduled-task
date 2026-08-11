import os
import requests

# 1. Đọc Cookie từ biến môi trường (Lấy từ GitHub Secrets)
cookie_str = os.getenv("MY_COOKIE")

# Kiểm tra nếu chưa cấu hình Secret
if not cookie_str:
    print("❌ Lỗi: Chưa cấu hình MY_COOKIE trong GitHub Secrets!")
    exit(1)

# 2. Cấu hình Headers gửi kèm Cookie và User-Agent (giả lập trình duyệt)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": cookie_str
}

# 3. URL trang web hoặc API bạn muốn gửi request
# (Thay URL bên dưới bằng URL thực tế bạn muốn lấy dữ liệu)
target_url = "https://httpbin.org/cookies"

# 4. Thực hiện gửi Request
try:
    print("Đang gửi request...")
    response = requests.get(target_url, headers=headers, timeout=10)
    
    print(f"Mã trạng thái (Status Code): {response.status_code}")
    print("Nội dung phản hồi (Response):")
    print(response.text[:500])
except Exception as e:
    print(f"❌ Có lỗi xảy ra: {e}")

import os
import requests

# 1. Đọc Cookie từ GitHub Secrets
cookie_str = os.getenv("MY_COOKIE")

if not cookie_str:
    print("❌ Lỗi: Chưa tìm thấy biến môi trường MY_COOKIE!")
    exit(1)

# 2. Cấu hình Headers giả lập trình duyệt
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": cookie_str
}

# 3. URL trang web/API bạn muốn gửi request (Thay URL bên dưới bằng URL của bạn)
target_url = "https://httpbin.org/cookies"

# 4. Thực hiện gửi Request
try:
    print("Đang gửi request...")
    response = requests.get(target_url, headers=headers, timeout=10)
    print(f"Mã trạng thái (Status Code): {response.status_code}")
    print("Nội dung phản hồi:")
    print(response.text[:500])
except Exception as e:
    print(f"❌ Có lỗi xảy ra: {e}")

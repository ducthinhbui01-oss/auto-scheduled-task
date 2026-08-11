import os
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def run():
    with sync_playwright() as p:
        print("1. Đang khởi chạy trình duyệt Chromium ngầm...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("2. Truy cập https://spx.shopee.vn/ ...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("3. Điền thông tin Đăng nhập...")
        # Tự động tìm và điền ô Username & Password
        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
        page.locator("input[type='password'], input[name='password']").first.fill(password)

        print("4. Bấm nút Đăng nhập...")
        page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()

        # Đợi 5 giây cho hệ thống xử lý đăng nhập và lưu Session Cookie
        page.wait_for_timeout(5000)

        print("5. Rút trích danh sách Cookie phiên làm việc mới...")
        cookies = context.cookies()
        
        # Ghép chuỗi Cookie theo định dạng chuẩn: name1=value1; name2=value2
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        print(f"Lấy thành công {len(cookies)} cookies từ SPX Shopee!")
        browser.close()

        # 6. Gửi Cookie thu được sang Google Trang tính
        print("6. Đang gửi chuỗi Cookie mới sang Google Trang tính...")
        payload = {
            "status": "Lấy Cookie SPX Thành Công",
            "result": cookie_string
        }
        
        sheet_res = requests.post(sheet_url, json=payload, timeout=30)
        print(f"Kết quả lưu vào Sheet: {sheet_res.text}")

if __name__ == "__main__":
    run()

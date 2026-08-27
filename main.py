import os
import time
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def run():
    print("⚡ Bắt đầu tiến trình lấy Cookie SPX...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Truy cập https://spx.shopee.vn/ ...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("2. Điền thông tin đăng nhập...")
        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
        page.locator("input[type='password'], input[name='password']").first.fill(password)
        
        print("3. Bấm nút Đăng nhập...")
        page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()
        page.wait_for_timeout(4000)

        # BƯỚC QUAN TRỌNG: Hoàn tất bước nhảy SSO chuyển tiếp về SPX
        print("4. Đang hoàn tất chuyển hướng SSO về SPX...")
        page.goto("https://spx.shopee.vn/api/admin/basicserver/ops_tob_login?refer=https://spx.shopee.vn/%23/", timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Rút trích toàn bộ cookie đầy đủ sau khi đã hoàn tất SSO
        cookies = context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        browser.close()

        # Đồng bộ các biến bắt buộc của SPX
        user_id = cookie_dict.get('fms_user_id') or cookie_dict.get('spx_uid') or ''
        user_key = cookie_dict.get('fms_user_skey') or cookie_dict.get('spx_uk') or ''

        if user_id:
            cookie_dict['spx_uid'] = str(user_id)
            cookie_dict['fms_user_id'] = str(user_id)
        if user_key:
            cookie_dict['spx_uk'] = str(user_key)
            cookie_dict['fms_user_skey'] = str(user_key)

        cookie_dict['spx_cid'] = 'VN'
        cookie_dict['spx_st'] = '1'
        cookie_dict['language'] = 'vi'
        cookie_dict['spx-lang'] = 'vi'
        cookie_dict['spx-admin-lang'] = 'vi'

        cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

        print(f"✅ Đăng nhập SPX thành công! (User ID: {user_id}, Tổng số Cookie: {len(cookie_dict)})")

        # Gửi chuỗi Cookie sang Google Sheets
        print("5. Đang lưu Cookie vào Google Sheets...")
        payload = {
            "status": "Lấy Cookie SPX Thành Công",
            "result": cookie_string
        }
        
        sheet_res = requests.post(sheet_url, json=payload, timeout=30)
        print(f"Kết quả lưu vào Sheet: {sheet_res.text}")

if __name__ == "__main__":
    run()

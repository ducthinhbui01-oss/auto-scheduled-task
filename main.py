import os
import time
import random
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def human_type(element, text):
    """Mô phỏng gõ phím từng ký tự với độ trễ ngẫu nhiên như người thật"""
    element.click()
    time.sleep(random.uniform(0.3, 0.6))
    for char in text:
        element.type(char, delay=random.randint(80, 180))
    time.sleep(random.uniform(0.2, 0.5))

def run():
    print("⚡ Bắt đầu mô phỏng thao tác người dùng để lấy Cookie SPX...")
    with sync_playwright() as p:
        print("1. Khởi chạy trình duyệt ẩn danh chống phát hiện bot...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        page = context.new_page()

        # Xóa dấu vết tự động hóa (Anti-Bot Bypass)
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => });
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        print("2. Truy cập trang đăng nhập SPX...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(1.0, 2.0))

        # Di chuột ngẫu nhiên mô phỏng người dùng
        page.mouse.move(random.randint(100, 400), random.randint(100, 300))
        time.sleep(0.5)

        print("3. Mô phỏng gõ tài khoản từng ký tự...")
        user_input = page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first
        human_type(user_input, username)

        print("4. Mô phỏng gõ mật khẩu từng ký tự...")
        pass_input = page.locator("input[type='password'], input[name='password']").first
        human_type(pass_input, password)

        # Rê chuột vào nút Đăng nhập
        print("5. Di chuột và bấm nút Đăng nhập...")
        login_btn = page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first
        login_btn.hover()
        time.sleep(random.uniform(0.4, 0.8))
        login_btn.click()

        # Chờ chuyển hướng tự nhiên sau đăng nhập
        print("-> Đang chờ chuyển hướng vào trang chủ...")
        try:
            page.wait_for_url(lambda u: "spx.shopee.vn" in u and "authenticate" not in u, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        time.sleep(4)

        # Mở trang phân hệ kho để kích hoạt bộ chìa khóa fms_user_skey
        print("6. Mở phân hệ SPX để nạp toàn bộ chìa khóa phiên...")
        page.goto("https://spx.shopee.vn/admin/transportation/trip", timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(4)

        # Rút trích toàn bộ cookie
        cookies = context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        browser.close()

        # Lấy User ID và Session Key
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

        print("\n---------------- KẾT QUẢ MÔ PHỎNG ----------------")
        print(f"User ID thu được: {'✅ ' + str(user_id) if user_id else '❌ RỖNG'}")
        print(f"Session Key (skey): {'✅ CÓ' if user_key else '❌ RỖNG'}")
        print(f"Tổng số Cookie hợp lệ: {len(cookie_dict)}")
        print("--------------------------------------------------\n")

        # Gửi sang Google Sheets
        print("7. Đang lưu Cookie vào Google Sheets...")
        payload = {
            "status": "Lấy Cookie SPX Thành Công",
            "result": cookie_string
        }
        
        sheet_res = requests.post(sheet_url, json=payload, timeout=30)
        print(f"Kết quả lưu vào Sheet: {sheet_res.text}")

if __name__ == "__main__":
    run()

import os

import time

import random

import requests

from playwright.sync_api import sync_playwright



username = os.getenv("USERNAME")

password = os.getenv("PASSWORD")

sheet_url = os.getenv("SHEET_URL")



# Nhận biết sự kiện kích hoạt (Chạy thủ công hay Lịch tự động)

event_name = os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch")



if not username or not password or not sheet_url:

    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")

    exit(1)



def run():

    # ------------------------------------------------------------------

    # NẾU BẤM RUN WORKFLOW THỦ CÔNG: BỎ QUA CHỜ (CHẠY NGAY TRONG 15s)

    # NẾU TỰ ĐỘNG THEO LỊCH 3H/LẦN: TẠM DỪNG NGẪU NHIÊN TỪ 5 ĐẾN 30 PHÚT

    # ------------------------------------------------------------------

    if event_name == "workflow_dispatch":

        print("⚡ Kích hoạt thủ công (Run workflow) -> Bỏ qua thời gian chờ, chạy ngay lập tức!")

    else:

        delay_seconds = random.randint(300, 1800) # Chờ ngẫu nhiên từ 5 đến 30 phút

        print(f"⏳ Chạy theo lịch tự động 3h/lần: Tạm dừng ngẫu nhiên {delay_seconds // 60} phút ({delay_seconds}s)...")

        time.sleep(delay_seconds)



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

        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)

        page.locator("input[type='password'], input[name='password']").first.fill(password)



        print("4. Bấm nút Đăng nhập...")

        page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()



        page.wait_for_timeout(5000)



        print("5. Rút trích danh sách Cookie phiên làm việc mới...")

        cookies = context.cookies()

        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        

        print(f"Lấy thành công {len(cookies)} cookies từ SPX Shopee!")

        browser.close()



        print("6. Đang gửi chuỗi Cookie mới sang Google Trang tính...")

        payload = {

            "status": "Lấy Cookie SPX Thành Công",

            "result": cookie_string

        }

        

        sheet_res = requests.post(sheet_url, json=payload, timeout=30)

        print(f"Kết quả lưu vào Sheet: {sheet_res.text}")



if __name__ == "__main__":

    run() 


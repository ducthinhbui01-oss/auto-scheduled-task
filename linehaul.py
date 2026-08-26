import os
import time
from datetime import datetime, timedelta
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def run():
    print("⚡ Bắt đầu tiến trình kéo dữ liệu Linehaul Trips...")
    with sync_playwright() as p:
        print("1. Khởi chạy trình duyệt Chromium ngầm...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("2. Đang truy cập và đăng nhập SPX...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")

        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
        page.locator("input[type='password'], input[name='password']").first.fill(password)
        page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()
        
        # Chờ đăng nhập hoàn tất
        page.wait_for_timeout(5000)

        # 3. Tính toán dải thời gian chuẩn: Từ hôm qua đến hết hôm nay
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        start_time = int(datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0).timestamp())
        end_time = int(datetime(now.year, now.month, now.day, 23, 59, 59).timestamp())

        linehaul_url = f"https://spx.shopee.vn/api/admin/transportation/trip/list_v2?station_type=2,3,7,12,14,16,18&trip_station_status=0&pageno=1&count=100&query_type=1&tab_type=3&std={start_time},{end_time}"

        # 4. Kéo dữ liệu Linehaul trực tiếp từ phiên trình duyệt Chromium
        print("3. Đang kéo dữ liệu Linehaul Trips từ API...")
        trip_res = page.evaluate("""async (url) => {
            try {
                const res = await fetch(url, {
                    headers: {
                        'app': 'FMS Portal',
                        'Accept': 'application/json, text/plain, */*'
                    }
                });
                return await res.json();
            } catch (e) {
                return { error: e.toString() };
            }
        }""", linehaul_url)

        trips = []
        if isinstance(trip_res, dict):
            trips = trip_res.get('data', {}).get('list') or trip_res.get('data', {}).get('trips') or []
        print(f"-> Lấy thành công {len(trips)} chuyến xe Linehaul!")

        browser.close()

        # 5. Gửi dữ liệu sang Google Sheets
        print("4. Đang gửi dữ liệu sang Google Trang tính...")
        payload = {
            "action": "sync_linehaul",
            "linehaul_trips": trips
        }
        
        res = requests.post(sheet_url, json=payload, timeout=60)
        print(f"Kết quả lưu vào Sheet: {res.text}")

if __name__ == "__main__":
    run()

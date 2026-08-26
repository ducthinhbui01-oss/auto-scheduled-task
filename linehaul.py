import os
import time
from datetime import datetime, timedelta, timezone
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
        page.wait_for_timeout(6000)

        # Múi giờ Việt Nam GMT+7
        tz_vn = timezone(timedelta(hours=7))
        now_vn = datetime.now(tz_vn)
        yesterday_vn = now_vn - timedelta(days=1)
        
        start_time = int(datetime(yesterday_vn.year, yesterday_vn.month, yesterday_vn.day, 0, 0, 0, tzinfo=tz_vn).timestamp())
        end_time = int(datetime(now_vn.year, now_vn.month, now_vn.day, 23, 59, 59, tzinfo=tz_vn).timestamp())

        linehaul_url = f"https://spx.shopee.vn/api/admin/transportation/trip/list_v2?station_type=2,3,7,12,14,16,18&trip_station_status=0&pageno=1&count=50&query_type=1&tab_type=3&std={start_time},{end_time}"
        print(f"3. Gọi API: {linehaul_url}")

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

        # In phản hồi thô từ SPX để kiểm tra cấu trúc
        print(f"-> Phản hồi thô từ SPX: {str(trip_res)[:500]}")

        trips = []
        if isinstance(trip_res, dict):
            data_obj = trip_res.get('data') or {}
            if isinstance(data_obj, list):
                trips = data_obj
            elif isinstance(data_obj, dict):
                trips = (data_obj.get('list') or 
                         data_obj.get('records') or 
                         data_obj.get('trips') or 
                         data_obj.get('trip_list') or 
                         data_obj.get('trip_station_list') or [])

        print(f"-> Đã bóc tách được: {len(trips)} chuyến xe Linehaul!")
        browser.close()

        if len(trips) == 0:
            print("⚠️ Không có chuyến xe nào để gửi.")
            return

        # Gửi dữ liệu sang Google Sheets
        print("4. Đang gửi dữ liệu sang Google Trang tính...")
        payload = {
            "action": "sync_linehaul",
            "linehaul_trips": trips
        }
        
        res = requests.post(sheet_url, json=payload, timeout=60)
        print(f"Kết quả lưu vào Sheet: {res.text}")

if __name__ == "__main__":
    run()

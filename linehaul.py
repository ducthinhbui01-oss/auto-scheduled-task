import os
import re
import time
import json
import math
import traceback
import concurrent.futures
from datetime import datetime, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

FROM_HOURS_AGO = 0
TO_HOURS_AFTER = 8

# DANH SÁCH 24 CỘT CẦN GIỮ LẠI
TARGET_COLUMNS = [
    "id", "trip_number", "trip_name", "schedule_id", "planning_name", "schedule_version",
    "label", "trip_station", "next_station_list", "next_station_name_list", "next_station_code_list",
    "vehicle_type", "vehicle_type_name", "origin_vehicle_type", "agency_id", "agency_name",
    "to_packed_quantity", "order_packed_quantity", "to_loaded_quantity", "order_loaded_quantity",
    "ctime", "mtime", "cost_type", "handover_enable"
]

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def format_trip_station(st_list, tz_vn):
    """Bóc tách mảng trip_station thành lộ trình trực quan: Trạm 1 (STD) ➔ Trạm 2 (STA)"""
    if not isinstance(st_list, list) or len(st_list) == 0:
        return ""
    parts = []
    for st in st_list:
        name = st.get('station_name') or str(st.get('station', ''))
        std = st.get('std', 0)
        sta = st.get('sta', 0)
        time_strs = []
        if std and std > 1000000000:
            time_strs.append(f"STD: {datetime.fromtimestamp(std, tz_vn).strftime('%d/%m %H:%M')}")
        if sta and sta > 1000000000:
            time_strs.append(f"STA: {datetime.fromtimestamp(sta, tz_vn).strftime('%d/%m %H:%M')}")
        time_info = f" ({' | '.join(time_strs)})" if time_strs else ""
        parts.append(f"{name}{time_info}")
    return " ➔ ".join(parts)

def format_item_to_row(item, tz_vn):
    """Chuẩn hóa dữ liệu 1 chuyến xe thành 1 hàng 24 cột sạch sẽ"""
    row = []
    for col in TARGET_COLUMNS:
        val = item.get(col)
        
        # 1. Bóc tách riêng cho cột trip_station
        if col == "trip_station":
            row.append(format_trip_station(val, tz_vn))
        
        # 2. Xóa bỏ dấu ngoặc vuông ["..."] cho các cột danh sách trạm kế tiếp
        elif col in ["next_station_list", "next_station_name_list", "next_station_code_list"]:
            if isinstance(val, list):
                row.append(", ".join(map(str, val)))
            else:
                row.append(str(val) if val is not None else "")
                
        # 3. Format thời gian ctime, mtime
        elif col in ["ctime", "mtime"] and isinstance(val, (int, float)) and val > 1000000000:
            val_str = datetime.fromtimestamp(val, tz_vn).strftime('%d/%m/%Y %H:%M:%S')
            row.append(val_str)
            
        # 4. Format Boolean
        elif isinstance(val, bool):
            row.append("TRUE" if val else "FALSE")
            
        # 5. Các dữ liệu còn lại
        elif isinstance(val, (dict, list)):
            row.append(json.dumps(val, ensure_ascii=False))
        else:
            row.append(str(val) if val is not None else "")
            
    return row

def fetch_page(page_no, base_url, req_headers):
    """Hàm tải 1 trang dữ liệu"""
    url = f"{base_url}&pageno={page_no}&count=100"
    try:
        res = requests.get(url, headers=req_headers, timeout=20)
        if res.status_code == 200:
            data = res.json()
            return data.get('data', {}).get('list') or data.get('data', {}).get('trips') or []
    except:
        pass
    return []

def run():
    tz_vn = timezone(timedelta(hours=7))
    now_vn = datetime.now(tz_vn)
    
    start_time = int((now_vn - timedelta(hours=FROM_HOURS_AGO)).timestamp())
    end_time = int((now_vn + timedelta(hours=TO_HOURS_AFTER)).timestamp())

    print(f"⚡ Bắt đầu kéo Linehaul Siêu Tốc (Giờ VN: {now_vn.strftime('%H:%M %d/%m/%Y')})")
    print(f"   -> Dải giờ lọc STD: từ {datetime.fromtimestamp(start_time, tz_vn).strftime('%H:%M %d/%m')} đến {datetime.fromtimestamp(end_time, tz_vn).strftime('%H:%M %d/%m')}")

    try:
        with sync_playwright() as p:
            print("1. Khởi chạy trình duyệt đăng nhập SPX...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            page.goto("https://spx.shopee.vn/", timeout=60000)
            page.wait_for_load_state("networkidle")

            page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
            page.locator("input[type='password'], input[name='password']").first.fill(password)
            
            login_btn = page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first
            login_btn.click()
            page.locator("input[type='password'], input[name='password']").first.press("Enter")

            # Chờ nhận token đăng nhập
            print("-> Đang chờ xác thực phiên...")
            user_id = ""
            user_key = ""
            cookie_dict = {}

            for i in range(20):
                time.sleep(1)
                cookies = context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                user_id = cookie_dict.get('fms_user_id') or cookie_dict.get('spx_uid') or ''
                user_key = cookie_dict.get('fms_user_skey') or cookie_dict.get('spx_uk') or ''
                if user_id:
                    print(f"-> Đăng nhập thành công (User ID: {user_id})")
                    break

            browser.close()

            # Đồng bộ Cookie
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
            csrf_token = cookie_dict.get('csrftoken', '')

            req_headers = {
                "app": "FMS Portal",
                "Cookie": cookie_string,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://spx.shopee.vn/admin/transportation/trip",
                "Origin": "https://spx.shopee.vn",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if csrf_token:
                req_headers["x-csrftoken"] = csrf_token

            base_api_url = f"https://spx.shopee.vn/api/admin/transportation/trip/list_v2?station_type=2,3,7,12,14,16,18&trip_station_status=0&query_type=1&tab_type=3&std={start_time},{end_time}"

            # 2. Tải trang 1 để tính tổng số trang
            print("2. Đang kiểm tra tổng số chuyến xe...")
            p1_res = requests.get(f"{base_api_url}&pageno=1&count=100", headers=req_headers, timeout=30).json()
            total_trips = p1_res.get('data', {}).get('total', 0)
            p1_trips = p1_res.get('data', {}).get('list') or p1_res.get('data', {}).get('trips') or []
            
            all_trips = list(p1_trips)
            total_pages = min(math.ceil(total_trips / 100), 50)

            print(f"-> Tổng cộng hệ thống có: {total_trips} chuyến xe (~{total_pages} trang).")

            # 3. Kéo đa luồng tất cả các trang còn lại
            if total_pages > 1:
                print(f"3. Đang mở 8 luồng kéo song song từ trang 2 đến {total_pages}...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    future_to_page = {
                        executor.submit(fetch_page, p_no, base_api_url, req_headers): p_no 
                        for p_no in range(2, total_pages + 1)
                    }
                    for future in concurrent.futures.as_completed(future_to_page):
                        res_list = future.result()
                        all_trips.extend(res_list)

            print(f"✅ Thu thập hoàn tất: {len(all_trips)} chuyến xe!")

            if len(all_trips) == 0:
                print("⚠️ Không có dữ liệu để gửi.")
                return

            # 4. Chuẩn hóa bóc tách dữ liệu 24 cột
            print("4. Đang bóc tách và định dạng dữ liệu 24 cột...")
            rows_data = [format_item_to_row(t, tz_vn) for t in all_trips]

            # 5. Gửi sang Google Sheets
            print("5. Đang gửi dữ liệu sang Google Sheets...")
            payload = {
                "action": "sync_linehaul_fast",
                "headers": TARGET_COLUMNS,
                "rows": rows_data
            }
            
            res = requests.post(sheet_url, json=payload, timeout=180)
            print(f"Kết quả lưu vào Sheet: {res.text}")

    except Exception as err:
        print(f"❌ Đã xảy ra lỗi: {err}")
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    run()

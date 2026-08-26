import os
import time
import json
import math
import traceback
from datetime import datetime, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

# Khung giờ: From 0 hrs ago ~ To 8 hrs after (Hiện tại -> 8 tiếng tới)
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
    """Bóc tách mảng trip_station thành lộ trình: Trạm 1 (STD) ➔ Trạm 2 (STA)"""
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
        
        if col == "trip_station":
            row.append(format_trip_station(val, tz_vn))
        elif col in ["next_station_list", "next_station_name_list", "next_station_code_list"]:
            if isinstance(val, list):
                row.append(", ".join(map(str, val)))
            else:
                row.append(str(val) if val is not None else "")
        elif col in ["ctime", "mtime"] and isinstance(val, (int, float)) and val > 1000000000:
            val_str = datetime.fromtimestamp(val, tz_vn).strftime('%d/%m/%Y %H:%M:%S')
            row.append(val_str)
        elif isinstance(val, bool):
            row.append("TRUE" if val else "FALSE")
        elif isinstance(val, (dict, list)):
            row.append(json.dumps(val, ensure_ascii=False))
        else:
            row.append(str(val) if val is not None else "")
            
    return row

def run():
    tz_vn = timezone(timedelta(hours=7))
    now_vn = datetime.now(tz_vn)
    
    start_time = int((now_vn - timedelta(hours=FROM_HOURS_AGO)).timestamp())
    end_time = int((now_vn + timedelta(hours=TO_HOURS_AFTER)).timestamp())

    print(f"⚡ Bắt đầu kéo Linehaul Toàn Bộ Các Hub (Giờ VN: {now_vn.strftime('%H:%M %d/%m/%Y')})")
    print(f"   -> Dải giờ lọc STD: từ {datetime.fromtimestamp(start_time, tz_vn).strftime('%H:%M %d/%m')} đến {datetime.fromtimestamp(end_time, tz_vn).strftime('%H:%M %d/%m')}")

    try:
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
            
            login_btn = page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first
            login_btn.click()
            
            # Chờ hoàn tất đăng nhập
            page.wait_for_timeout(8000)

            # Bao phủ toàn bộ station_type để kéo đủ tất cả các Hub
            all_station_types = "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20"
            api_query = f"station_type={all_station_types}&trip_station_status=0&query_type=1&tab_type=3&std={start_time},{end_time}"

            print("3. Đang kéo song song toàn bộ các trang dữ liệu từ SPX...")
            
            # KÉO SONG SONG TRỰC TIẾP QUA PHIÊN TRÌNH DUYỆT (SIÊU NHANH & KHÔNG BỊ 401)
            fetch_result = page.evaluate("""async (query) => {
                try {
                    // Tải trang 1 để lấy tổng số chuyến
                    const p1Url = '/api/admin/transportation/trip/list_v2?' + query + '&pageno=1&count=100';
                    const res1 = await fetch(p1Url);
                    const data1 = await res1.json();
                    
                    const total = data1?.data?.total || 0;
                    let allList = data1?.data?.list || data1?.data?.trips || [];
                    
                    const totalPages = Math.min(Math.ceil(total / 100), 40);
                    
                    // Kéo song song các trang còn lại
                    if (totalPages > 1) {
                        const pagePromises = [];
                        for (let p = 2; p <= totalPages; p++) {
                            const pUrl = '/api/admin/transportation/trip/list_v2?' + query + '&pageno=' + p + '&count=100';
                            pagePromises.push(
                                fetch(pUrl)
                                    .then(r => r.json())
                                    .then(d => d?.data?.list || d?.data?.trips || [])
                                    .catch(() => [])
                            );
                        }
                        const results = await Promise.all(pagePromises);
                        results.forEach(subList => {
                            allList = allList.concat(subList);
                        });
                    }
                    return { total: total, trips: allList };
                } catch (e) {
                    return { error: e.toString() };
                }
            }""", api_query)

            browser.close()

            if isinstance(fetch_result, dict) and fetch_result.get("error"):
                print(f"⚠️ Lỗi fetch trong trình duyệt: {fetch_result.get('error')}")

            all_trips = fetch_result.get("trips", []) if isinstance(fetch_result, dict) else []
            total_count = fetch_result.get("total", len(all_trips)) if isinstance(fetch_result, dict) else len(all_trips)

            print(f"✅ Thu thập thành công: {len(all_trips)}/{total_count} chuyến xe từ tất cả các Hub!")

            if len(all_trips) == 0:
                print("⚠️ Cảnh báo: Không có chuyến xe nào trong khung giờ này.")
                return

            # 4. Bóc tách và chuẩn hóa dữ liệu 24 cột
            print("4. Đang bóc tách và định dạng 24 cột dữ liệu...")
            rows_data = [format_item_to_row(t, tz_vn) for t in all_trips]

            # 5. Gửi sang Google Sheets
            print("5. Đang gửi dữ liệu siêu tốc sang Google Sheets...")
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

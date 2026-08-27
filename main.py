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
    print("================ BẮT ĐẦU TIẾN TRÌNH LẤY & KIỂM TRA COOKIE SPX ================")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Truy cập https://spx.shopee.vn/ ...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("2. Điền thông tin tài khoản và đăng nhập...")
        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
        page.locator("input[type='password'], input[name='password']").first.fill(password)
        
        login_btn = page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first
        login_btn.click()
        page.wait_for_timeout(5000)

        # BƯỚC QUAN TRỌNG: Điều hướng vào trang nội bộ để SPX kích hoạt fms_user_id & fms_user_skey
        print("3. Đang chuyển tiếp vào phân hệ SPX để nạp toàn bộ khóa phiên...")
        page.goto("https://spx.shopee.vn/admin/transportation/trip", timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(4)

        # Rút trích cookie đầy đủ
        cookies = context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        browser.close()

    # BƯỚC 4: ĐỒNG BỘ VÀ TỔNG HỢP CHUỖI COOKIE
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

    print(f"\n-> Đã tổng hợp {len(cookie_dict)} khóa Cookie (User ID: {user_id or 'Chưa thấy'}, Skey: {'Có' if user_key else 'Không'})")

    # =========================================================================
    # BƯỚC 5: TỰ ĐỘNG GỌI THỬ VÀO API SPX ĐỂ KIỂM TRA ĐỘ SỐNG CỦA COOKIE (LIVE TEST)
    # =========================================================================
    print("4. Đang gọi thử nghiệm trực tiếp vào API SPX (Workstation)...")
    test_api_url = "https://spx.shopee.vn/api/wfm/admin/workstation/assignment/history/list?pageno=1&count=1"
    test_headers = {
        "Cookie": cookie_string,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        test_res = requests.get(test_api_url, headers=test_headers, timeout=20)
        res_json = test_res.json() if test_res.status_code == 200 else {}
        retcode = res_json.get("retcode")

        if test_res.status_code == 200 and retcode != 401:
            print(f"🎉 XÁC THỰC THÀNH CÔNG: Cookie HOẠT ĐỘNG HOÀN HẢO 100% (Mã HTTP: 200, retcode: {retcode})!")
            
            # Gửi Cookie đã xác thực thành công về Google Sheets
            print("5. Đang gửi Cookie sống về Google Sheets...")
            payload = {
                "status": "Lấy Cookie SPX Thành Công",
                "result": cookie_string
            }
            sheet_res = requests.post(sheet_url, json=payload, timeout=30)
            print(f"Kết quả lưu vào Sheet: {sheet_res.text}")
        else:
            print(f"⚠️ XÁC THỰC THẤT BẠI: API trả về HTTP {test_res.status_code}, retcode: {retcode}. Nội dung: {test_res.text[:300]}")
            print("-> Không gửi Cookie không hợp lệ về Google Sheets để tránh lỗi bảng tính.")
            exit(1)

    except Exception as e:
        print(f"❌ Lỗi trong quá trình kiểm tra API: {e}")
        exit(1)

    print("================ HOÀN TẤT TIẾN TRÌNH ================\n")

if __name__ == "__main__":
    run()

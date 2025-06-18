import time
import subprocess
import re
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
USER_DATA_DIR = r"C:\\Users\\HP\\chrome_automation_profile"

def launch_chrome():
    subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check"
    ])
    print("🚀 Chrome launched with remote debugging...")
    time.sleep(5)

def css_escape(value):
    return re.sub(r'([!"#$%&\'()*+,./:;<=>?@[\\]^`{|}~])', r'\\\\\\1', value)

def search_symbol(page, symbol):
    print(f"🔍 Searching for symbol: {symbol}")
    page.keyboard.press("Control+K")
    page.wait_for_timeout(500)
    page.keyboard.type(symbol)
    page.wait_for_timeout(1500)
    page.keyboard.press("Enter")
    page.wait_for_timeout(5000)
    page.keyboard.press("Escape")  # Close search popup
    print(f"✅ Opened chart for {symbol}")

def open_settings_and_set_timezone(page, timezone_id="Australia/Sydney"):
    try:
        print("⚙️ Clicking Settings button...")
        page.click("button#header-toolbar-properties", timeout=5000)
        page.wait_for_timeout(1000)

        print("🌐 Opening timezone dropdown...")
        page.click("span#id_candleSymbolTimezone_options-dropdown", timeout=3000)
        page.wait_for_timeout(1000)

        escaped_id = css_escape(f"id_candleSymbolTimezone_options-dropdown_item_{timezone_id}")
        selector = f"#{escaped_id}"
        print(f"🧭 Selecting timezone with selector: {selector}")

        option = page.locator(selector)
        option.scroll_into_view_if_needed()
        option.wait_for(state="visible", timeout=5000)
        option.click()
        print(f"✅ Timezone set to {timezone_id}")

        page.click("button:has-text('Ok')")
        print("✅ Clicked OK to apply timezone")
    except Exception as e:
        print("❌ Failed to set timezone:", e)

def main():
    symbol = "AUDCAD"
    timezone_id = "Australia/Sydney"

    launch_chrome()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        print("🌍 Opening TradingView...")
        page.goto("https://www.tradingview.com", timeout=60000)
        page.wait_for_timeout(7000)

        search_symbol(page, symbol)
        open_settings_and_set_timezone(page, timezone_id)

        input("🕹️ Press Enter to close...")

if __name__ == "__main__":
    main()

import json
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime

TRADINGVIEW_URL = "https://www.tradingview.com/"
USER_DATA_DIR = "backend/user-data/tradingview-session"
TRIGGER_DATA_FILE = "trigger_data.json"
NODEJS_BACKEND_URL = "http://localhost:5000"

def get_tradingview_credentials(jwt_token):
    """Get TradingView credentials from Node.js backend"""
    try:
        headers = {'Authorization': f'Bearer {jwt_token}'}
        response = requests.get(f"{NODEJS_BACKEND_URL}/api/profile/tradingview-credentials/decrypt", headers=headers)
        
        if response.status_code == 200:
            creds = response.json()
            print("✅ Retrieved TradingView credentials from backend")
            return creds['email'], creds['password']
        else:
            print(f"❌ Failed to get credentials: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"❌ Error fetching credentials: {e}")
        return None, None

def check_if_logged_in(page):
    """Check if user is already logged in to TradingView"""
    try:
        # Look for the anonymous user menu button - if exists, user is not logged in
        anonymous_button = page.locator("button.tv-header__user-menu-button--anonymous")
        if anonymous_button.is_visible(timeout=3000):
            print("🔒 User not logged in - login required")
            return False
        else:
            print("✅ User already logged in")
            return True
    except:
        # If we can't find anonymous button, assume logged in
        print("✅ Assuming user is logged in")
        return True

def perform_login(page, username, password):
    """Perform automatic login to TradingView"""
    try:
        print(f"🔐 Starting login process for user: {username}")
        
        # Step 1: Click on the anonymous user menu button
        anonymous_button = page.locator("button.tv-header__user-menu-button--anonymous")
        anonymous_button.click()
        page.wait_for_timeout(2000)
        print("👤 Clicked on user menu button")
        
        # Step 2: Click on "Sign in" option in the dropdown
        sign_in_button = page.locator("text=Sign in").first
        sign_in_button.click()
        page.wait_for_timeout(3000)
        print("🔑 Clicked on Sign in option")
        
        # Step 3: Fill in the login form
        # Fill username/email field
        username_input = page.locator("input#id_username")
        username_input.wait_for(timeout=1000000)
        username_input.fill(username)
        page.wait_for_timeout(500)
        print(f"📧 Filled username: {username}")
        
        # Fill password field
        password_input = page.locator("input#id_password")
        password_input.fill(password)
        page.wait_for_timeout(500)
        print("🔒 Filled password")
        
        # Step 4: Click the Sign in button
        submit_button = page.locator("button.submitButton-LQwxK8Bm")
        submit_button.click()
        print("🚀 Clicked Sign in button")
        
        # Wait for login to complete
        page.wait_for_timeout(5000000)
        
        # Check if login was successful
        if check_if_logged_in(page):
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed - still seeing login form")
            return False
            
    except Exception as e:
        print(f"❌ Login process failed: {e}")
        return False

def open_tradingview():
    try:
        # Load trigger data
        with open(TRIGGER_DATA_FILE, "r") as f:
            data = json.load(f)
            print("📦 Trigger data received:", data)
    except Exception as e:
        print("❌ Failed to load trigger data:", e)
        return

    # Extract JWT token from trigger data (sent by frontend)
    jwt_token = data.get("jwt_token")
    if not jwt_token:
        print("❌ No JWT token found in trigger data")
        return

    # Get TradingView credentials from Node.js backend
    username, password = get_tradingview_credentials(jwt_token)
    if not username or not password:
        print("❌ Could not retrieve TradingView credentials")
        return

    print("🚀 Opening TradingView...")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            slow_mo=100,
            args=[
                "--disable-session-crashed-bubble",     # Remove restore popup
                "--no-default-browser-check"            # No default browser warning
            ]
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(TRADINGVIEW_URL)
        page.wait_for_timeout(6000)
        print("🌐 TradingView.com opened")

        # Check if user is logged in, if not perform login
        if not check_if_logged_in(page):
            if not perform_login(page, username, password):
                print("❌ Login failed - cannot proceed")
                return
            page.wait_for_timeout(3000)

        print("✅ TradingView is ready and user is logged in.")
        
        # Get symbol/script name from trigger data
        symbol = data.get("symbol", "GOLD")
        
        # Step: Search for symbol using Ctrl+K
        try:
            print(f"🔍 Searching for symbol: {symbol}")
            page.keyboard.press("Control+K")
            page.wait_for_timeout(2000)
            
            # Wait for search input to appear and type the symbol
            search_input = page.locator("input[type='search']").first
            search_input.wait_for(timeout=10000)
            search_input.fill(symbol)
            page.wait_for_timeout(1000)
            
            # Press Enter to select the symbol
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)
            
            print(f"✅ Symbol '{symbol}' searched and selected!")
            
        except Exception as e:
            print(f"❌ Symbol search failed: {e}")
        
        # Get timeframe from trigger data
        timeframe = data.get("timeframe", "5")
        
        # Step: Set timeframe using keyboard shortcut
        try:
            print(f"⏱️ Setting timeframe to: {timeframe}")
            
            # Press each digit of the timeframe (e.g., "15" -> press "1" then "5")
            for digit in timeframe:
                page.keyboard.press(digit)
                page.wait_for_timeout(200)
            
            # Press Enter to apply the timeframe
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
            
            print(f"✅ Timeframe '{timeframe}' set successfully!")
            
        except Exception as e:
            print(f"❌ Timeframe setting failed: {e}")
        
        # Get start_time and end_time from trigger data
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        if start_time and end_time:
            draw_trendline_between_times(
                page,
                start_time,
                end_time,
                data.get("trendline_color"),
                data.get("price")
            )
        else:
            print("⚠️ No start_time/end_time provided — skipping trendline drawing.")
        
        print("🎯 You can now manually navigate and use TradingView as needed.")
        
        # Keep the browser open for user interaction
        input("Press Enter to close the browser...")

def draw_trendline_between_times(page, start_time_str, end_time_str, color_hex, price):
    """Full trendline drawing: go to start, activate, click, go to end, click, style."""
    try:
        print("✏️ Starting full trendline placement...")

        # Parse strings to datetime
        dt_start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        dt_end = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")

        # 🟢 Step 1: Go to start date/time first
        go_to_datetime(page, dt_start.strftime("%Y-%m-%d"), dt_start.strftime("%H:%M"))
        page.wait_for_timeout(3000)

        # 🟢 Step 2: THEN activate trendline tool
        page.keyboard.press("Alt+T")
        page.wait_for_timeout(1000)

        # 🟢 Step 3: Click to start trendline
        canvas = page.locator("canvas[data-name='pane-top-canvas']").first
        box = canvas.bounding_box()
        # Shift right by 60px to account for TradingView's left-shifted chart view (approx. 45 minutes or 3 candles on 15m chart)
        adjusted_x = box["x"] + (box["width"] // 2) + 60
        center_y = box["y"] + box["height"] // 2
        page.mouse.click(adjusted_x, center_y)
        page.wait_for_timeout(1000)

        # 🟢 Step 4: Go to end date/time
        go_to_datetime(page, dt_end.strftime("%Y-%m-%d"), dt_end.strftime("%H:%M"))
        page.wait_for_timeout(3000)

        # 🟢 Step 5: Click to end trendline
        canvas = page.locator("canvas[data-name='pane-top-canvas']").first
        box = canvas.bounding_box()
        # Shift right by 60px to account for TradingView's left-shifted chart view (approx. 45 minutes or 3 candles on 15m chart)
        adjusted_x = box["x"] + (box["width"] // 2) + 60
        center_y = box["y"] + box["height"] // 2
        page.mouse.click(adjusted_x, center_y)
        page.wait_for_timeout(1000)

        # 🟢 Step 6: Style it
        set_trendline_color(page, color_hex, adjusted_x, center_y, price)

    except Exception as e:
        print(f"❌ Failed to draw full trendline: {e}")


def get_type_from_color(color_hex):
    color_map = {
        "#000000": "open",
        "#FFA500": "close",
        "#FF0000": "high",
        "#00FF00": "low"
    }
    return color_map.get(color_hex.upper(), "open")

def draw_trendline_at_center(page, color_hex, price=None):
    """Draw a trend line at the center of the chart after Alt+G navigation and set its color if provided."""
    try:
        print("✏️ Drawing trend line at center of chart...")
        # Step 1: Activate trend line tool
        page.keyboard.press("Alt+T")
        page.wait_for_timeout(1000)

        # Step 2: Find all canvases with the correct data-name and pick the largest
        canvases = page.locator("canvas[data-name='pane-top-canvas']")
        count = canvases.count()
        largest_box = None
        largest_area = 0
        for i in range(count):
            canvas = canvases.nth(i)
            canvas.wait_for(state="visible", timeout=10000)
            box = canvas.bounding_box()
            if box:
                area = box["width"] * box["height"]
                if area > largest_area:
                    largest_area = area
                    largest_box = box

        if not largest_box:
            print("❌ Could not find chart canvas for trend line.")
            return

        # Step 3: Calculate center position
        center_x = largest_box["x"] + largest_box["width"] // 2
        center_y = largest_box["y"] + largest_box["height"] // 2

        # Step 4: Click to start the trend line (100 pixels to the left of center)
        page.mouse.move(center_x - 100, center_y)
        page.mouse.down()
        page.mouse.up()
        page.wait_for_timeout(300)

        # Step 5: Move and click again to finish the trend line (100 pixels to the right of center)
        page.mouse.move(center_x + 100, center_y)
        page.mouse.down()
        page.mouse.up()
        page.wait_for_timeout(300)

        # Step 6: Press Enter to confirm the trend line
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)
        print("✅ Trend line drawn at center of chart.")

        # Step 7: Set color if provided
        set_trendline_color(page, color_hex, center_x, center_y, price)
    except Exception as e:
        print(f"❌ Failed to draw trend line: {e}")

def set_trendline_color(page, color_hex, center_x, center_y, price=None):
    try:
        print(f"🎨 Setting trendline color to {color_hex}")
        # 1. Wait for the floating toolbar to appear (after drawing the trendline)
        page.wait_for_timeout(1000)
        # 2. Click the settings (gear) button in the floating toolbar
        settings_button = page.locator("div.floating-toolbar-react-widgets__button[data-name='settings']").first
        settings_button.click()
        page.wait_for_timeout(1000)
        # Always switch to the Style tab before setting color
        style_tab = page.locator("button#style, [data-id='source-properties-editor-tabs-style']").first
        style_tab.click()
        page.wait_for_timeout(300)
        # 3. Click the color swatch to open the color picker
        color_swatch = page.locator("div.swatch-Sw_a4qpB").first
        color_swatch.click()
        page.wait_for_timeout(500)
        # 4. Click the 'Add custom color' button
        add_custom_button = page.locator("button.customButton-mdcOkvbj").first
        add_custom_button.click()
        page.wait_for_timeout(300)
        # 5. The hex input is already focused. Clear it and type the new hex code.
        page.keyboard.press('Control+A')
        page.keyboard.press('Backspace')
        page.keyboard.type(color_hex)
        page.wait_for_timeout(200)
        # 6. Click the 'Add' button by its text content
        add_button = page.locator("button.button-D4RPB3ZC.primary-D4RPB3ZC").filter(has_text="Add").first
        add_button.click()
        page.wait_for_timeout(300)
        print("✅ Trendline color set!")

        # 7. Click the Text tab and wait for the textarea to be visible
        text_tab = page.locator("button#text, [data-id='source-properties-editor-tabs-text']").first
        text_tab.click()
        page.wait_for_timeout(500)
        # Specifically target the textarea inside the container
        textarea = page.locator(".container-WDZ0PRNh textarea.textarea-x5KHDULU").first
        textarea.wait_for(state="visible", timeout=2000)
        textarea.click()
        page.wait_for_timeout(100)
        # 8. Type the label (type/price) in the textarea
        if price is not None:
            trendline_type = get_type_from_color(color_hex)
            label = f"{trendline_type}/{price}"
            textarea.fill("")
            page.wait_for_timeout(100)
            textarea.type(label)
            page.wait_for_timeout(200)
        print(f"✅ Trendline text set: {label}")

        # 9. Click the Coordinates tab
        coordinates_tab = page.locator("button#coordinates, [data-id='source-properties-editor-tabs-coordinates']").first
        coordinates_tab.click()
        page.wait_for_timeout(500)
        # 10. Set both price fields to the value of price
        if price is not None:
            price_inputs = page.locator("input[name='y-input'].input-RUSovanF")
            price_inputs.nth(0).click()
            price_inputs.nth(0).fill(str(price))
            page.wait_for_timeout(100)
            price_inputs.nth(1).click()
            price_inputs.nth(1).fill(str(price))
            page.wait_for_timeout(100)
        # 11. Wait 1 second, then click Ok
        page.wait_for_timeout(1000)
        ok_button = page.locator("button:has-text('Ok')").first
        ok_button.click()
        page.wait_for_timeout(500)
        print("✅ Trendline coordinates set and confirmed!")
    except Exception as e:
        print(f"❌ Failed to set trendline color, text, or coordinates: {e}")

def go_to_datetime(page, date, time):
    """Set either date or time using Alt+G popup in TradingView."""
    try:
        if date:
            print(f"🕒 Going to date: {date}")
            page.keyboard.press("Alt+G")
            page.wait_for_timeout(1000)

            # Date input is already focused
            date_input = page.locator("input.input-RUSovanF[data-qa-id='ui-lib-Input-input']").first
            date_input.fill("")
            date_input.type(date)
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

        if time:
            print(f"🕒 Going to time: {time}")
            page.keyboard.press("Alt+G")
            page.wait_for_timeout(1000)

            # Time input is second input
            time_input = page.locator("input.input-RUSovanF[data-qa-id='ui-lib-Input-input']").nth(1)
            time_input.click()
            time_input.fill("")
            time_input.type(time)
            page.wait_for_timeout(300)

            go_to_button = page.locator("button:has-text('Go to')")
            if go_to_button.is_visible(timeout=2000):
                go_to_button.click()
            else:
                page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

        print(f"✅ Chart moved to {date or ''} {time or ''}")
    except Exception as e:
        print(f"❌ Failed to go to date/time: {e}")

if __name__ == "__main__":
    open_tradingview()
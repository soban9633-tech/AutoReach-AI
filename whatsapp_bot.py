import os
import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class WhatsAppBot:
    def __init__(self, profile_dir=None):
        import tempfile
        self.driver = None
        if os.environ.get('VERCEL'):
            self.profile_dir = profile_dir or os.path.join(tempfile.gettempdir(), "whatsapp_chrome_profile")
        else:
            self.profile_dir = profile_dir or os.path.abspath("./whatsapp_chrome_profile")
        try:
            os.makedirs(self.profile_dir, exist_ok=True)
        except Exception:
            pass

    def start_browser(self):
        """
        Launches Google Chrome with saved profile so login persists.
        """
        if self.driver:
            try:
                # Test if browser is still responsive
                _ = self.driver.current_url
                return True
            except Exception:
                self.close()

        options = Options()
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")
        # Keep window open
        options.add_experimental_option("detach", True)

        # Remove stale lock if Chrome crashed earlier
        for lock_name in ['SingletonLock', 'lockfile']:
            lf = os.path.join(self.profile_dir, lock_name)
            if os.path.exists(lf):
                try:
                    os.remove(lf)
                except Exception:
                    pass

        try:
            # First try default installed chromedriver if available or webdriver-manager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get("https://web.whatsapp.com")
            return True
        except Exception as e:
            # Fallback direct
            try:
                self.driver = webdriver.Chrome(options=options)
                self.driver.get("https://web.whatsapp.com")
                return True
            except Exception as ex:
                raise RuntimeError(f"Could not open Chrome: {str(ex)}")

    def is_logged_in(self, timeout=10):
        """
        Checks if WhatsApp Web is logged in.
        """
        if not self.driver:
            return False
        try:
            # Look for common WhatsApp elements that indicate login (chat list, search bar, side menu)
            selectors = [
                "//div[@contenteditable='true'][@data-tab='3']",  # search input
                "//header[@data-testid='chatlist-header']",
                "//div[@id='pane-side']",
                "//span[@data-icon='chat']",
                "//span[@data-icon='menu']"
            ]
            for sel in selectors:
                elems = self.driver.find_elements(By.XPATH, sel)
                if elems and len(elems) > 0 and elems[0].is_displayed():
                    return True
            return False
        except Exception:
            return False

    def get_qr_code(self):
        """
        Captures the QR code image from WhatsApp Web and returns it as a base64 string.
        """
        if not self.driver:
            return None
        try:
            # 1. Try finding canvas directly
            canvases = self.driver.find_elements(By.TAG_NAME, "canvas")
            for c in canvases:
                try:
                    if c.is_displayed() and c.size['width'] > 80:
                        return c.screenshot_as_base64
                except Exception:
                    continue

            # 2. Try QR container
            containers = self.driver.find_elements(By.XPATH, "//div[@data-ref] | //div[contains(@class, '_akau')] | //div[contains(@class, 'landing-wrapper')] | //div[@aria-label]")
            for qc in containers:
                try:
                    if qc.is_displayed() and qc.size['width'] > 120:
                        return qc.screenshot_as_base64
                except Exception:
                    continue

            return None
        except Exception:
            return None

    def wait_for_login(self, max_wait_seconds=120, status_callback=None):
        """
        Waits for user to scan QR code and log in.
        """
        if not self.driver:
            self.start_browser()

        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            if self.is_logged_in():
                if status_callback:
                    status_callback("WhatsApp Web logged in successfully!")
                return True
            if status_callback:
                status_callback("Please scan QR code in the opened Chrome window...")
            time.sleep(3)
        return False

    def send_message(self, phone_number, message_text, wait_timeout=35):
        """
        Sends message to a single phone number.
        Returns: (bool success, str detail)
        """
        if not self.driver:
            return False, "Browser is not running"

        if not phone_number:
            return False, "Empty or invalid phone number"

        encoded_text = urllib.parse.quote(message_text or "")
        url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_text}"
        
        try:
            self.driver.get(url)
        except Exception as e:
            return False, f"Navigation failed: {str(e)}"

        # Wait for either the send button, chat input, or error popup
        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            # 1. Check for "invalid phone number" popup
            try:
                invalid_popups = self.driver.find_elements(
                    By.XPATH, 
                    "//div[contains(text(), 'Phone number shared via url is invalid') or contains(text(), 'URL is invalid') or contains(text(), 'The phone number')] | //div[@role='dialog']//button"
                )
                if invalid_popups:
                    for p in invalid_popups:
                        text = p.text.lower()
                        if 'invalid' in text or 'ok' in text:
                            # Click OK to dismiss dialog
                            try:
                                p.click()
                            except Exception:
                                pass
                            return False, "Phone number is not on WhatsApp or invalid"
            except Exception:
                pass

            # 2. Check for send button (airplane icon / send icon)
            try:
                send_buttons = self.driver.find_elements(
                    By.XPATH, 
                    "//span[@data-icon='send']/parent::button | //button[@aria-label='Send'] | //button[@data-testid='compose-btn-send']"
                )
                if send_buttons and send_buttons[0].is_displayed():
                    send_buttons[0].click()
                    time.sleep(2)  # Wait for message dispatch
                    return True, "Message sent successfully"
            except Exception:
                pass

            # 3. Check for message input area and press ENTER
            try:
                inputs = self.driver.find_elements(
                    By.XPATH, 
                    "//div[@contenteditable='true'][@data-tab='10'] | //footer//div[@contenteditable='true']"
                )
                if inputs and inputs[0].is_displayed():
                    # Wait briefly so pre-filled text is settled
                    time.sleep(1)
                    inputs[0].send_keys(Keys.ENTER)
                    time.sleep(2)
                    return True, "Message sent successfully"
            except Exception:
                pass

            time.sleep(1.5)

        return False, "Timeout waiting for WhatsApp chat to open"

    def close(self):
        """Closes browser session."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

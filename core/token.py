import json
import secrets
import urllib.parse
import webbrowser
import requests
from typing import Dict, List, Optional

CLIENT_ID = "2882303761517383915"
OAUTH_AUTH_URL = (
    "https://account.xiaomi.com/oauth2/authorize"
    "?skip_confirm=false"
    f"&client_id={CLIENT_ID}&pt=0"
    "&scope=1+6000+16001+20000"
    "&redirect_uri=https%3A%2F%2Fhm.xiaomi.com%2Fwatch.do"
    "&_locale=en_US"
    "&response_type=code"
)

LOGIN_URL = "https://account.huami.com/v2/client/login"

class AuthKeyExtractor:
    @staticmethod
    def get_login_url() -> str:
        return OAUTH_AUTH_URL

    @staticmethod
    def open_browser():
        print("[*] Opening Xiaomi account login page in your default browser...")
        webbrowser.open(OAUTH_AUTH_URL)

    @staticmethod
    def extract_from_redirect_url(redirect_url: str, country_code: str = "SG") -> List[Dict]:
        """
        Takes the redirect URL containing ?code=... and queries Huami / Zepp cloud
        to extract registered devices and their 16-byte Bluetooth Auth Keys.
        """
        parsed = urllib.parse.urlparse(redirect_url.strip())
        query = urllib.parse.parse_qs(parsed.query)
        if "code" not in query:
            raise ValueError("URL does not contain a valid 'code' parameter.")
        code = query["code"][0]
        
        # Step 1: Exchange code for Huami apptoken
        device_id = "02:00:00:%02x:%02x:%02x" % (secrets.randbelow(255), secrets.randbelow(255), secrets.randbelow(255))
        payload = {
            "dn": "account.huami.com,api-user.huami.com,app-analytics.huami.com,api-watch.huami.com,api-analytics.huami.com,api-mifit.huami.com",
            "app_version": "5.9.2-play_100355",
            "source": "com.huami.watch.hmwatchmanager",
            "third_name": "mi-watch",
            "lang": "en",
            "country_code": country_code,
            "device_model": "android_phone",
            "allow_registration": "false",
            "app_name": "com.huami.midong",
            "grant_type": "request_token",
            "device_id": device_id,
            "code": code
        }
        
        resp = requests.post(LOGIN_URL, data=payload, timeout=10)
        data = resp.json()
        
        if "error_code" in data:
            raise RuntimeError(f"Login failed: Error {data['error_code']}")
            
        if "token_info" not in data:
            raise RuntimeError("Failed to receive token info from Xiaomi cloud.")
            
        token_info = data["token_info"]
        app_token = token_info["app_token"]
        user_id = urllib.parse.quote(token_info["user_id"])
        
        # Step 2: Query device registry
        # Determine endpoint based on country code / token prefix
        devices_url = f"https://api-mifit-us2.huami.com/users/{user_id}/devices"
        dev_resp = requests.get(
            devices_url,
            params={"enableMultiDevice": "true"},
            headers={"apptoken": app_token},
            timeout=10
        )
        dev_data = dev_resp.json()
        
        devices = []
        if "items" in dev_data:
            for item in dev_data["items"]:
                info = json.loads(item.get("additionalInfo", "{}"))
                auth_key = info.get("auth_key", "")
                devices.append({
                    "mac": item.get("macAddress", ""),
                    "auth_key": auth_key,
                    "product_id": info.get("productId", -1),
                    "device_source": info.get("deviceSource", -1)
                })
        return devices

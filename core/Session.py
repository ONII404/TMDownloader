# /core/Session.py
import requests
import urllib3

# Desactivar warnings de SSL si decides no verificar
urllib3.disable_warnings()

class SessionManager:
    def __init__(self, cookies_file=None):
        self.session = self._create_session(cookies_file)
    
    def _create_session(self, cookies_file):
        try:
            import cloudscraper
            s = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "android", "mobile": True},
                delay=3
            )
        except ImportError:
            s = requests.Session()

        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Poco X6 Pro) AppleWebKit/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
        })

        if cookies_file:
            self._load_cookies(s, cookies_file)
        
        return s

    def _load_cookies(self, session, path):
        try:
            import http.cookiejar
            jar = http.cookiejar.MozillaCookieJar(path)
            jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies.update(jar)
        except Exception as e:
            print(f"[!] Error cargando cookies: {e}")

    def get_session(self):
        return self.session
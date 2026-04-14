import re
import time
import requests
from bs4 import BeautifulSoup

# ── Tentative import Selenium ──────────────────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

# ── Tentative import Playwright ────────────────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False


# ==============================================================================
# CONFIG
# ==============================================================================
URL = "https://example.com/contact"
WAIT_SECONDS = 3          # temps d'attente rendu JS
HEADLESS = True           # False = ouvre un vrai navigateur (debug)


# ==============================================================================
# EXTRACTION (commune à toutes les méthodes)
# ==============================================================================
def extract_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")

    # --- Emails ---
    mailto_emails = {
        a["href"].replace("mailto:", "").strip()
        for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I))
    }
    text_emails = set(re.findall(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text
    ))
    emails = mailto_emails | text_emails

    # --- Téléphones ---
    raw_phones = re.findall(
        r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{1,4}\)?[\s.\-]?)(?:\d{2,4}[\s.\-]?){3,6}\d{2,4}",
        text
    )
    phones = {p.strip() for p in raw_phones if len(re.sub(r"\D", "", p)) >= 8}

    # --- Noms / Prénoms ---
    name_candidates = set()

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b",
                               "p", "span", "div"]):
        attrs = " ".join([
            " ".join(tag.get("class", [])),
            tag.get("id", "")
        ]).lower()
        if any(kw in attrs for kw in ["name", "nom", "contact", "person",
                                       "author", "auteur", "prenom", "staff",
                                       "member", "equipe", "team"]):
            name = tag.get_text(separator=" ").strip()
            if name:
                name_candidates.add(name)

    regex_names = re.findall(
        r"\b([A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ][a-zàâéèêëîïôùûüç'-]+)\s+"
        r"([A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ][A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ'-]{1,}|"
        r"[A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ][a-zàâéèêëîïôùûüç'-]+)\b",
        text
    )
    for prenom, nom in regex_names:
        name_candidates.add(f"{prenom} {nom}")

    return {"emails": emails, "phones": phones, "names": name_candidates}


# ==============================================================================
# MÉTHODE 1 — requests (statique, rapide)
# ==============================================================================
def fetch_with_requests(url: str) -> str | None:
    print("[1] Tentative avec requests...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        print("    OK")
        return r.text
    except Exception as e:
        print(f"    Échec : {e}")
        return None


# ==============================================================================
# MÉTHODE 2 — Selenium (JS rendu via Chrome)
# ==============================================================================
def fetch_with_selenium(url: str) -> str | None:
    if not SELENIUM_OK:
        print("[2] Selenium non installé — ignoré")
        return None
    print("[2] Tentative avec Selenium...")
    try:
        opts = ChromeOptions()
        if HEADLESS:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("user-agent=Mozilla/5.0")

        driver = webdriver.Chrome(options=opts)
        driver.get(url)

        # Attend que le body soit chargé + laisse le JS s'exécuter
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(WAIT_SECONDS)

        html = driver.page_source
        driver.quit()
        print("    OK")
        return html
    except Exception as e:
        print(f"    Échec : {e}")
        return None


# ==============================================================================
# MÉTHODE 3 — Playwright (JS rendu, plus robuste)
# ==============================================================================
def fetch_with_playwright(url: str) -> str | None:
    if not PLAYWRIGHT_OK:
        print("[3] Playwright non installé — ignoré")
        return None
    print("[3] Tentative avec Playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context(
                user_agent="Mozilla/5.0",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(WAIT_SECONDS * 1000)
            html = page.content()
            browser.close()
        print("    OK")
        return html
    except Exception as e:
        print(f"    Échec : {e}")
        return None


# ==============================================================================
# AFFICHAGE
# ==============================================================================
def print_results(data: dict, method: str):
    print(f"\n{'='*50}")
    print(f"  Résultats — méthode : {method}")
    print(f"{'='*50}")

    print("\n=== Emails ===")
    for e in sorted(data["emails"]) or ["(aucun)"]:
        print(f"  {e}")

    print("\n=== Téléphones ===")
    for p in sorted(data["phones"]) or ["(aucun)"]:
        print(f"  {p}")

    print("\n=== Noms détectés ===")
    for n in sorted(data["names"]) or ["(aucun)"]:
        print(f"  {n}")


# ==============================================================================
# PIPELINE — essaie les 3 méthodes, s'arrête dès qu'une réussit
# ==============================================================================
def run():
    # Requests → Selenium → Playwright
    for fetch_fn, label in [
        (fetch_with_requests,  "requests"),
        (fetch_with_selenium,  "Selenium"),
        (fetch_with_playwright,"Playwright"),
    ]:
        html = fetch_fn(URL)
        if html:
            data = extract_data(html)
            # Si on n'a rien trouvé, essaie la méthode suivante (JS probable)
            if not any(data.values()):
                print("    Aucune donnée extraite, essai méthode suivante...")
                continue
            print_results(data, label)
            return

    print("\nAucune méthode n'a permis d'extraire des données.")


if __name__ == "__main__":
    run()

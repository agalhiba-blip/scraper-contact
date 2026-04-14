from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
from bs4 import BeautifulSoup


def extract_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")

    # Emails
    mailto_emails = {
        a["href"].replace("mailto:", "").strip()
        for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I))
    }
    text_emails = set(re.findall(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text
    ))
    emails = mailto_emails | text_emails

    # Téléphones
    raw_phones = re.findall(
        r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{1,4}\)?[\s.\-]?)(?:\d{2,4}[\s.\-]?){3,6}\d{2,4}",
        text
    )
    phones = {p.strip() for p in raw_phones if len(re.sub(r"\D", "", p)) >= 8}

    # Noms
    name_candidates = set()
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b", "p", "span", "div"]):
        attrs = " ".join([" ".join(tag.get("class", [])), tag.get("id", "")]).lower()
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

    return {"emails": sorted(emails), "phones": sorted(phones), "names": sorted(name_candidates)}


def fetch(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15, verify=False)
    r.raise_for_status()
    return r.text


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        url = params.get("url", [None])[0]

        if not url:
            self._respond(400, {"error": "Paramètre 'url' manquant. Usage: /api/scrape?url=https://site.com"})
            return

        try:
            html = fetch(url)
            data = extract_data(html)
            self._respond(200, {"url": url, **data})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode())

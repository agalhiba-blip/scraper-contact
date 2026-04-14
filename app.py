from flask import Flask, request, jsonify
from scraper_contact import extract_data, fetch_with_requests, fetch_with_playwright

app = Flask(__name__)


@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Paramètre 'url' manquant"}), 400

    # Essaie requests d'abord, puis Playwright si JS nécessaire
    html = fetch_with_requests(url)
    if not html or not any(extract_data(html).values()):
        html = fetch_with_playwright(url)

    if not html:
        return jsonify({"error": "Impossible de charger la page"}), 500

    data = extract_data(html)
    return jsonify({
        "url": url,
        "emails": sorted(data["emails"]),
        "phones": sorted(data["phones"]),
        "names":  sorted(data["names"]),
    })


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "usage": "/scrape?url=https://site.com/contact"})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

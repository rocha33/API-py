from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright

import time

CACHE = {}
CACHE_TTL = 30

app = FastAPI(title="Extractor M3U8 API")

def extract_m3u8_network(url: str):
    m3u8_links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
    ]
        )

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"
        )

        # 👇 captura qualquer request .m3u8
        def on_request(request):
            req_url = request.url
            if ".m3u8" in req_url:
                m3u8_links.append(req_url)

        page.on("request", on_request)

        page.goto(url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(3000)

        browser.close()

    return list(set(m3u8_links))


@app.get("/extract")
def extract(url: str):
    now = time.time()

    if url in CACHE:
        data, ts = CACHE[url]
        if now - ts < CACHE_TTL:
            return data

    links = extract_m3u8_network(url)

    if not links:
        raise HTTPException(404, "Nenhum m3u8 detectado")

    response = {
        "status": "ok",
        "count": len(links),
        "m3u8": links
    }

    CACHE[url] = (response, now)
    return response
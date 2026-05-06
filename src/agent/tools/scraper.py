import httpx
from bs4 import BeautifulSoup

TIMEOUT = 10


def scrape(url: str) -> dict:
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
    except Exception as exc:
        return {"url": url, "content": "", "error": str(exc)}
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return {"url": url, "content": text[:3000]}

"""Extract visible text and links from fetched HTML pages."""

from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class PageData:
    title: str
    text: str
    links: list[str]


def parse_page(html: bytes | str) -> PageData:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    links = [href for tag in soup.find_all("a", href=True) if (href := tag.get("href"))]
    for tag in soup.find_all(["script", "style", "nav", "footer"]):
        tag.decompose()
    return PageData(title=title, text=soup.get_text(" ", strip=True), links=links)


from pathlib import Path
from bs4 import BeautifulSoup, Tag
from typing import Generator, Tuple, List
from tqdm import tqdm
from dataclasses import dataclass

import mimetypes
import requests
import ebook

TITLE_SELECTOR = r".entry-title"
CONTENT_SELECTOR = r".entry-content"

WORM_START_URL = r"https://parahumans.wordpress.com/2011/06/11/1-1/"

@dataclass
class WormChapter:
    title: Tag
    content: Tag

def get_page(url: str) -> BeautifulSoup:
    ans = requests.get(url)
    if not ans.ok:
        raise RuntimeError(f"failed getting {url}")

    return BeautifulSoup(ans.text, features="lxml")


def worm_chapters(url: str) -> Generator[WormChapter, None, None]:
    while True:
        page = get_page(url)

        title = page.select_one(TITLE_SELECTOR)
        content = page.select_one(CONTENT_SELECTOR)

        if title is None or content is None:
            raise RuntimeError("failed finding chapter title or content")

        yield WormChapter(title, content)

        next_page_link = page.select_one(r'a[rel="next"]')
        if next_page_link is None:
            return

        url = str(next_page_link["href"])


def get_image(url: str) -> bytes:
    img_ans = requests.get(url)
    if not img_ans.ok:
        raise RuntimeError(f"failed getting image from {url}")
    
    return img_ans.content


def parse_chapter(chapter: WormChapter) -> Tuple[ebook.Chapter, List[ebook.Resource]]:
    resources: List[ebook.Resource] = []

    for img in chapter.content.find_all("img"):
        img_type = mimetypes.guess_type(img["src"])[0]
        if img_type is None:
            raise RuntimeError("failed gussing img mime type")
        
        image_bytes = get_image(img["src"])
        resources.append(ebook.Resource(image_bytes, img_type, Path(img["src"]).suffix[1:]))
        img["src"] = resources[-1].filename

    return ebook.Chapter(chapter.title.text.replace("#", "_"), "".join([str(t) for t in chapter.content.children])), resources


def parse_book(title: str, author: str) -> ebook.Book:
    book = ebook.Book(title, author=author)

    with tqdm() as t:
        for chapter in worm_chapters(WORM_START_URL):
            t.set_description(f"Parsing {chapter.title.text}")
            book_chapter, chapter_resources = parse_chapter(chapter)

            for resource in chapter_resources:
                book.add_ebook_resource(resource)

            book.add_chapter(book_chapter)

    return book


def main():
    book = parse_book("Worm", "Wildbow")
    book.write_ebook("worm.epub")

if __name__ == "__main__":
    main()
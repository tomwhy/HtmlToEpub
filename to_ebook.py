from pathlib import Path
from bs4 import BeautifulSoup, Tag
from typing import Generator, Tuple, List, Union
from tqdm import tqdm
from dataclasses import dataclass

import re
import mimetypes
import requests
import ebook

TITLE_SELECTOR = r".entry-title"
CONTENT_SELECTOR = r".entry-content"

WORM_START_URL = r"https://parahumans.wordpress.com/2011/06/11/1-1/"

def select_tag(html: BeautifulSoup, selector: str) -> Tag:
    tag = html.select_one(selector)

    if tag is None:
        raise RuntimeError(f"failed finding {selector}")
    
    return tag


def get_image(url: str) -> bytes:
    img_ans = requests.get(url)
    if not img_ans.ok:
        raise RuntimeError(f"failed getting image from {url}")
    
    return img_ans.content

class WormChapter:
    def __init__(self, page: BeautifulSoup):
        self._ebook_chapter: Union[ebook.Chapter, None] = None
        self._resources: List[ebook.Resource] = []

        self._title = select_tag(page, TITLE_SELECTOR)
        self._content: Tag = select_tag(page, CONTENT_SELECTOR)

        if self._title is None or self._content is None:
            raise RuntimeError("failed finding chapter title or content")

    def __filter_content_tags(self):
        for tag in self._content.find_all("a", string=re.compile("Chapter")):
            tag.extract()
    
        for tag in self._content.find_all(id="jp-post-flair"):
            tag.extract()

    def __extract_images(self):
        for img in self._content.find_all("img"):
            img_type = mimetypes.guess_type(img["src"])[0]
            if img_type is None:
                raise RuntimeError("failed gussing img mime type")
            
            image_bytes = get_image(img["src"])
            image_ext = Path(img["src"]).suffix[1:]
            self._resources.append(ebook.Resource(image_bytes, img_type, image_ext))
            img["src"] = self._resources[-1].filename
        
    def __parse(self):
        self.__filter_content_tags()
        self.__extract_images()

        self._ebook_chapter = ebook.Chapter(self.title, "".join((str(t) for t in self._content.children)))

    @property
    def title(self) -> str:
        return self._title.text

    @property
    def ebook_chapter(self) -> ebook.Chapter:
        if self._ebook_chapter is None:
            self.__parse()
        
        assert self._ebook_chapter is not None
        return self._ebook_chapter

    @property
    def resources(self) -> List[ebook.Resource]:
        if not self._resources:
            self.__parse()

        return self._resources


def get_page(url: str) -> BeautifulSoup:
    ans = requests.get(url)
    if not ans.ok:
        raise RuntimeError(f"failed getting {url}")

    return BeautifulSoup(ans.text, features="lxml")


def worm_chapters(url: str) -> Generator[WormChapter, None, None]:
    while True:
        page = get_page(url)
        yield WormChapter(page)

        next_page_link = page.select_one(r'a[rel="next"]')
        if next_page_link is None:
            return

        url = str(next_page_link["href"])


def parse_book(title: str, author: str) -> ebook.Book:
    book = ebook.Book(title, author=author)

    with tqdm() as t:
        for chapter in worm_chapters(WORM_START_URL):
            t.set_description(f"Parsing {chapter.title}")

            for resource in chapter.resources:
                book.add_ebook_resource(resource)

            book.add_chapter(chapter.ebook_chapter)

            t.update()

    return book


def main():
    book = parse_book("Worm", "Wildbow")
    book.write_ebook("worm.epub")

if __name__ == "__main__":
    main()
from pathlib import Path
from bs4 import BeautifulSoup, Tag
from typing import Generator, Tuple, List, Union
from tqdm import trange
from dataclasses import dataclass

import re
import mimetypes
import requests
import ebook

TITLE_SELECTOR = r".entry-title"
CONTENT_SELECTOR = r".entry-content"
POST_FLAIR_SELECTOR = r"#jp-post-flair"

WORM_START_URL = r"https://parahumans.wordpress.com/2011/06/11/1-1/"
WORM_TOC_URL = r"https://parahumans.wordpress.com/table-of-contents/"

ARC_REGEX = re.compile(r"^(?P<arc_name>\w+)\s+(?P<arc_num>(?:\d+|e).*?(?:.\d+)?)\s*(?:\(.*?\))?$")

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
    
        for tag in self._content.select(POST_FLAIR_SELECTOR):
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
    def arc(self) -> str:
        match = ARC_REGEX.match(self.title)

        # a special case that the regex does not catch
        if match is None and self.title == "Interlude: End":
            return "Interlude"

        assert match is not None and match["arc_name"] is not None
        return match["arc_name"]

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


def get_worm_num_chapters() -> int:
    toc_page = get_page(WORM_TOC_URL)

    toc = select_tag(toc_page, CONTENT_SELECTOR)
    return len(re.findall(r"(?:\d+|E)\.(?:\d+|\w)", toc.text))


def worm_chapters() -> Generator[WormChapter, None, None]:
    url = WORM_START_URL
    
    with trange(get_worm_num_chapters()) as t:
        for _ in t:
            page = get_page(url)
            chapter = WormChapter(page)
            
            t.set_description(f"Parsing {chapter.title}")
            yield chapter
            
            next_page_link = page.select_one(r'a[rel="next"]')
            if next_page_link is None:
                raise RuntimeError("failed getting next page url")

            url = str(next_page_link["href"])


def parse_book(title: str, author: str) -> ebook.Book:
    book = ebook.Book(title, author=author)
    current_arc = ""
    arc_chapters: List[ebook.Chapter] = []

    for chapter in worm_chapters():
        if chapter.arc != current_arc and chapter.arc != "Interlude":
            if arc_chapters:
                book.add_section(current_arc, arc_chapters)

            arc_chapters = []
            current_arc = chapter.arc

        for resource in chapter.resources:
            book.add_ebook_resource(resource)

        arc_chapters.append(chapter.ebook_chapter)

    # add the last arc
    if arc_chapters:
        book.add_section(current_arc, arc_chapters)

    return book


def main():
    book = parse_book("Worm", "Wildbow")
    book.write_ebook("worm.epub")

if __name__ == "__main__":
    main()
from ebooklib import epub
from typing import List, Union
from dataclasses import dataclass
from pathlib import Path

SECTION_PAGE_TEMPLATE = "<div class=section_page>{name}</div>"

@dataclass
class Chapter:
    title: str
    content: str

class Resource:
    def __init__(self, content: bytes, type: str, ext: str):
        self._content = content
        self._type = type
        self._ext = ext

    @property
    def filename(self):
        return f"resources/{str(hash(self._content))}.{self._ext}"
    
    @property
    def content(self):
        return self._content
    
    @property
    def type(self):
        return self._type


class Book:
    def __init__(self, title: str, lang: str = "en", author: str = ""):
        self._book = epub.EpubBook()

        self._book.set_title(title)
        self._book.set_language(lang)

        book_id = str(hash(title + author))
        self._book.set_identifier(book_id)

        if author:
            self._book.add_author(author)
            
        self._book_css = epub.EpubItem(file_name="style/ebook.css", media_type="text/css", content=Path("css/ebook.css").read_bytes())
        self._book.add_item(self._book_css)
        
        self._book.spine = ['nav']
        self._book.toc = []

        self._resources = {}


    def __create_epub_chapter(self, chapter: Chapter, include_title: bool = True) -> epub.EpubHtml:
        chapter_filename = f"{hash(chapter.title)}.xhtml"
        epub_chapter = epub.EpubHtml(title=chapter.title, file_name=chapter_filename)
        epub_chapter.add_item(self._book_css)

        content = chapter.content
        if include_title:
            content = f"<div class=title>{chapter.title}</div>{content}"
        epub_chapter.set_content(content)

        self._book.add_item(epub_chapter)
        return epub_chapter

    def add_ebook_resource(self, resource: Resource):
        item = epub.EpubItem(file_name=resource.filename, media_type=resource.type, content=resource.content)
        self._resources[resource.filename] = item

    def add_chapter(self, chapter: Chapter):
        epub_chapter = self.__create_epub_chapter(chapter)

        self._book.spine.append(epub_chapter)
        self._book.toc.append(epub.Link(epub_chapter.file_name, chapter.title, chapter.title))

    def add_section(self, name: str, chapters: List[Chapter]):
        epub_chapters = [self.__create_epub_chapter(c) for c in chapters]
        section_page = self.__create_epub_chapter(Chapter(name, SECTION_PAGE_TEMPLATE.format(name=name)), include_title=False)

        self._book.toc.append((epub.Section(name, href=section_page.file_name), epub_chapters))
        self._book.spine.append(section_page)
        self._book.spine.extend(epub_chapters)

    def write_ebook(self, path: str):
        for resource in self._resources.values():
            self._book.add_item(resource)

        self._book.add_item(epub.EpubNcx())
        self._book.add_item(epub.EpubNav())

        epub.write_epub(path, self._book)

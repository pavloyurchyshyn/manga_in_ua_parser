import argparse
import asyncio
import httpx
import logging
import os
import requests
import shutil
import sys
import time
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Union
from urllib.parse import urljoin
from pdf_merger import MangaPDFMerger


def get_default_logger(lvl: int = logging.INFO,
                       format_: str = '%(asctime)s - %(levelname)s - %(message)s') -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(lvl)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(lvl)

    formatter = logging.Formatter(format_)
    stdout_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)
    return logger


class MangaInUaParser:
    BASE_URL: str = 'https://manga.in.ua'
    MANGAS_SUB_URL: str = urljoin(BASE_URL, 'mangas')
    CHAPTER_LINKS_CLASS: str = 'forfastnavigation chapterscalc'
    CHAPTER_URL_ATTR: str = 'href'
    IMAGE_URL_ATTR: str = 'data-src'

    DOWNLOAD_ATTEMPTS = 10

    def __init__(self, manga_url: str, base_url: str = None,
                 data_folder: Union[str, Path, None] = None,
                 logger: logging.Logger = None):
        self.logger = logger if logger else get_default_logger()

        if manga_url.startswith(self.MANGAS_SUB_URL):
            self.manga_url = manga_url
        else:
            self.manga_url = urljoin(self.MANGAS_SUB_URL, manga_url)

        self.base_url: str = str(base_url) if base_url else self.BASE_URL

        if data_folder:
            self.data_folder: Path = Path(data_folder)

        else:
            self.data_folder: Path = Path(__file__).parent / f'{manga_url.split("/")[-1].replace(".html", "")}_data'

        if not self.data_folder.exists():
            self.data_folder.mkdir()

        self.errors = []

    def get_chapters_links(self) -> List[str]:
        soup = BeautifulSoup(requests.get(self.manga_url).content, features='html.parser')
        links = [el[self.CHAPTER_URL_ATTR] for el in soup.find_all(class_=self.CHAPTER_LINKS_CLASS)]
        self.logger.debug(f'Found links: {", ".join(links)}')
        return links

    def get_images_urls(self, chapter_url: str) -> List[str]:
        images_urls = []
        for attempt in range(0, self.DOWNLOAD_ATTEMPTS + 1):
            resp = requests.get(chapter_url)
            soup = BeautifulSoup(resp.content, features='html.parser')
            images_urls = [el[self.IMAGE_URL_ATTR] for el in soup.find_all(attrs={self.IMAGE_URL_ATTR: True})]
            if not images_urls:
                self.logger.warning(f'{resp.status_code} - {chapter_url} {attempt}/{self.DOWNLOAD_ATTEMPTS}')
                if resp.status_code == 429 and attempt != self.DOWNLOAD_ATTEMPTS:
                    self.logger.warning(f' Too many requests {chapter_url}. Sleep.')
                    time.sleep(5)
                    continue

                raise Exception(
                    f'No images found. ({resp.status_code}){soup.find_all(attrs={self.IMAGE_URL_ATTR: True})}')
            else:
                break

        return images_urls

    def ping_site(self) -> int:
        self.logger.info(f'Pinging {self.base_url}')
        return requests.get(self.base_url).status_code

    @staticmethod
    def save_img(path: Path, data: bytes) -> None:
        with open(path, 'wb') as f:
            f.write(data)

    async def async_download_image(self, img_url: str, img_path: Path, downloaded_string: str = '') -> None:
        start = time.time()
        async with httpx.AsyncClient() as client:
            for attempt in range(0, self.DOWNLOAD_ATTEMPTS + 1):
                try:
                    response = await client.get(img_url)
                except Exception as e:
                    self.logger.warning(f'Error during chapter {downloaded_string}({img_url}) image download.\n{e}')
                    if attempt == self.DOWNLOAD_ATTEMPTS:
                        self.logger.error(f'Failed to download: {img_url}')
                else:
                    if response.status_code == 404:
                        self.logger.error(f'Unable to download {img_url}(reason {response.status_code})')
                        self.errors.append(f'{img_url} unable to download({response.status_code})')
                        break
                    self.save_img(img_path, response.content)
                    self.logger.debug(f'Downloaded {downloaded_string}({round(time.time() - start, 2)} sec)')
                    break

    @staticmethod
    async def __gather_coroutines(*coroutines: Union[asyncio.Task, 'Coroutine']):
        await asyncio.gather(*coroutines)

    def download_images(self, images_links: List[str], chapter_folder: Path, chapter_string: str):
        coroutines = []

        for img, img_url in enumerate(images_links, start=1):
            downloaded_string = f'{chapter_string} - image {img}/{len(images_links)}'
            img_url = urljoin(self.base_url, img_url)
            img_path = chapter_folder / f'{img}.{img_url.split(".")[-1]}'
            coroutines.append(self.async_download_image(img_url=img_url,
                                                        img_path=img_path,
                                                        downloaded_string=downloaded_string))

        asyncio.run(self.__gather_coroutines(*coroutines))

    def download_chapter(self, url: str, chapter_folder: Path, chapter_string: str = ''):
        start = time.time()
        images_urls = self.get_images_urls(url)

        self.download_images(images_links=images_urls,
                             chapter_folder=chapter_folder,
                             chapter_string=chapter_string)
        self.logger.info(f'Chapter {chapter_string} downloaded, '
                         f'{len(images_urls)} images within {round(time.time() - start, 2)} sec.')

    def parse(self, forced: bool = False):
        try:
            self.check_data_folder_for_content()
        except FileExistsError:
            if forced:
                self.logger.info(f'Deleting {self.data_folder}')
                shutil.rmtree(self.data_folder)

        chapters_urls = self.get_chapters_links()

        self.logger.debug(f'Found chapters links: {", ".join(chapters_urls)}')
        self.data_folder.mkdir(exist_ok=True)
        global_start = time.time()

        for i, url in enumerate(chapters_urls, start=1):
            chapter_string = f'{i}/{len(chapters_urls)}'
            chapter_folder = self.data_folder / str(i)
            chapter_folder.mkdir()

            self.download_chapter(url=url, chapter_folder=chapter_folder, chapter_string=chapter_string)

        self.logger.info(f'All chapters({len(chapters_urls)}) '
                         f'downloaded within {time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - global_start))}.')

    def check_data_folder_for_content(self):
        if self.data_folder.exists() and os.listdir(self.data_folder):
            raise FileExistsError(f'Folder {self.data_folder} already exists and contain files.')

    def download_image_by_chapter_and_index(self, chapter: int, img: int):
        chapter_url = self.get_chapters_links()[chapter - 1]
        chapter_folder = self.data_folder / str(chapter)
        if not chapter_folder.exists():
            chapter_folder.mkdir()

        img_url = urljoin(self.base_url, self.get_images_urls(chapter_url)[img - 1])
        file_path = chapter_folder / str(img)
        self.logger.info(f'Downloading image {chapter}-{img}({img_url}) to {file_path}')

        asyncio.run(self.__gather_coroutines(self.async_download_image(img_url=img_url,
                                                                       img_path=file_path,
                                                                       downloaded_string=str(img))))


def parse_args() -> argparse.Namespace:
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument('--manga_url', '-url', type=str, required=True,
                             help='Example: boyovik/2252-berserk-berserk.html')
    args_parser.add_argument('--result_folder', type=str, default=None,
                             help='The path where to store the result chapters pdfs.')
    args_parser.add_argument('--base_url', type=str, help='Base url.', default=MangaInUaParser.BASE_URL)
    args_parser.add_argument('--data_folder', '-d', type=str, default=None,
                             help='The path where to store downloaded images')

    args_parser.add_argument('--result_pdf', '-pdf', type=str, default=None,
                             help='The path where to store the result pdf.')
    args_parser.add_argument('--one_file', action='store_true', default=False,
                             help='Merge all manga in single pdf.')

    args_parser.add_argument('--keep_temp', action='store_true', help='Keep temp folder.', default=False)
    args_parser.add_argument('--keep_data', action='store_true', default=False,
                             help='Keep folder with downloaded images.')

    args_parser.add_argument('--force', action='store_true', help='Delete folder if exists', default=False)
    args_parser.add_argument('--resolution', '-r', type=float, help='PDF resolution.', default=100.)

    args_parser.add_argument('--log_level', choices=tuple(range(0, 51, 10)),
                             help='Log level', default=logging.INFO)

    return args_parser.parse_args()


def main():
    start = time.time()
    args = parse_args()

    logger = get_default_logger(args.log_level)
    parser = MangaInUaParser(manga_url=args.manga_url,
                             base_url=args.base_url,
                             data_folder=args.data_folder,
                             logger=logger)
    parser.parse(forced=args.force)

    result_pdf = args.result_pdf if args.result_pdf else f"{args.manga_url.split('/')[-1].split('.')[-2]}.pdf"
    result_folder = args.result_folder if args.result_folder else args.manga_url.split('/')[-1].split('.')[-2]
    pdf_merge = MangaPDFMerger(result_folder=result_folder,
                               data_folder=parser.data_folder,
                               logger=logger,
                               resolution=args.resolution,
                               result_pdf=result_pdf,
                               )

    pdf_merge.merge(args.force, delete_temp=not args.keep_temp, merge_to_one_pdf=args.one_file)

    if not args.keep_data:
        logger.info(f'Deleting data folder: {parser.data_folder}')
        shutil.rmtree(parser.data_folder)

    logger.info(f'Done in {time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start))}')


if __name__ == '__main__':
    main()

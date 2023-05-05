import os
import shutil
import time
from logging import Logger
from multiprocessing import Pool, cpu_count
from pathlib import Path

import PyPDF2.errors
from PIL import Image
from PyPDF2 import PdfMerger
from typing import List


def convert_image_to_pdf(img_path: Path, pdf_path: Path, resolution: float = 100.):
    try:
        with open(pdf_path, 'wb') as f:
            Image.open(Path(img_path)).convert('RGB').save(f, "PDF", resolution=resolution)
    except PyPDF2.errors.EmptyFileError:
        raise Exception(f'Unable to convert an empty file: {img_path}')


def sort_function(file_path: Path) -> int:
    return int(file_path.parent.name) * 1000 + int(file_path.name.replace(file_path.suffix, ''))


class MangaPDFMerger:
    PROCESSES: int = cpu_count()
    TEMPORARY_FOLDER_NAME: str = 'temp'

    def __init__(self, result_folder: Path,
                 data_folder: Path,
                 logger: Logger,
                 result_pdf: Path = None,
                 img_formats: tuple = ('.jpg', '.png', '.webp'),
                 resolution: float = 100.0):

        self.result_folder: Path = Path(result_folder)
        if result_pdf:
            self.result_pdf: Path = Path(result_pdf)
        else:
            self.result_pdf: Path = self.result_folder.parent / f'{self.result_folder.name}.pdf'

        if not self.result_folder.is_absolute():
            self.result_folder = Path(os.getcwd(), self.result_folder)

        self.logger: Logger = logger
        self.base_folder: Path = Path(data_folder)
        self.img_formats = img_formats
        self.resolution: float = resolution

    def collect_images_in_folder(self, folder: Path) -> List[Path]:
        images: List[Path] = []
        for file in os.listdir(folder):
            file = folder / str(file)
            if file.suffix in self.img_formats:
                images.append(file)

        images.sort(key=sort_function)
        return images

    def convert_images_in_folder_to_pdf(self, folder: Path, result_pdf: Path = None):
        folder = Path(folder)
        start = time.time()
        images: List[Path] = self.collect_images_in_folder(folder)

        if not images:
            self.logger.warning(f'No images in {folder}')
            return

        result_pdf = Path(result_pdf) if result_pdf else self.result_folder
        result_pdf.parent.mkdir(parents=True, exist_ok=True)

        temp_folder = self.base_folder.parent / self.TEMPORARY_FOLDER_NAME / folder.name
        temp_folder.mkdir(exist_ok=True, parents=True)

        pdfs = []
        pool = Pool(processes=self.PROCESSES)
        for i, image_path in enumerate(images, start=1):
            pdf_path = temp_folder / f'{image_path.parent.name}_{image_path.name}.pdf'
            pdfs.append(pdf_path)
            pool.apply_async(convert_image_to_pdf,
                             kwds=dict(img_path=image_path, pdf_path=pdf_path, resolution=self.resolution))

        pool.close()
        pool.join()
        self.merge_pdfs(*pdfs, result_pdf=result_pdf)
        self.logger.info(f'Created pdf {result_pdf} from {folder}({len(images)} imgs)'
                         f' in {round(time.time() - start, 2)} sec.')

    @staticmethod
    def merge_pdfs(*pdfs: Path, result_pdf: Path):
        pdf_merger = PdfMerger()
        try:
            for pdf_path in pdfs:
                pdf_merger.append(pdf_path)

            with open(result_pdf, 'wb') as f:
                pdf_merger.write(f)
        except Exception:
            raise Exception(f'Unable to convert an empty file: {pdf_path}')

        finally:
            pdf_merger.close()

    def merge(self, force: bool = False, delete_temp: bool = True, merge_to_one_pdf: bool = False):
        start = time.time()

        temp_folder: Path = self.base_folder.parent / self.TEMPORARY_FOLDER_NAME
        chapters_folder = self.result_folder

        if force and chapters_folder.exists():
            shutil.rmtree(chapters_folder)

        try:
            self.convert_images_in_folder_to_pdf(self.base_folder, result_pdf=chapters_folder / '0.pdf')
            chapters_folders = []
            for f in sorted(os.listdir(self.base_folder), key=lambda p: int(Path(p).name)):
                f: Path = self.base_folder / f
                if f.is_dir():
                    chapters_folders.append(f)

            for i, folder_path in enumerate(chapters_folders, start=1):
                self.convert_images_in_folder_to_pdf(folder=folder_path, result_pdf=chapters_folder / f'{i}.pdf')
                self.logger.info(f'{i}/{len(chapters_folders)} chapter generated to {chapters_folder / f"{i}.pdf"}')

            if merge_to_one_pdf:
                pdfs = [chapters_folder / f for f in os.listdir(chapters_folder)]
                self.logger.info(f'Merging into one pdf - {self.result_pdf}: {", ".join(map(str, pdfs))}')
                self.merge_pdfs(*pdfs, result_pdf=self.result_pdf)
                self.logger.info(f'Result one pdf stored in {self.result_pdf}')
        except Exception as e:
            self.logger.error(f'{e}. {folder_path}')
            raise e
        finally:
            if delete_temp:
                self.logger.debug(f'Deleting temp: {temp_folder}')
                shutil.rmtree(temp_folder)

        self.logger.info(f'Finished within {round(time.time() - start, 2)} sec')
        self.logger.info(f'Result stored in {self.result_folder}')


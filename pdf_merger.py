import os
import shutil
import time
from logging import Logger
from multiprocessing import Pool, cpu_count
from pathlib import Path
from PIL import Image
from PyPDF2 import PdfMerger
from typing import List


def convert_image_to_pdf(img_path: Path, pdf_path: Path, resolution: float = 100.):
    with open(pdf_path, 'wb') as f:
        Image.open(Path(img_path)).convert('RGB').save(f, "PDF", resolution=resolution)


def sort_function(file_path: Path) -> int:
    return int(file_path.parent.name) * 1000 + int(file_path.name.replace(file_path.suffix, ''))


class MangaPDFMerger:
    PROCESSES: int = cpu_count()
    TEMPORARY_FOLDER_NAME: str = 'temp'

    def __init__(self, result_file: Path,
                 data_folder: Path,
                 logger: Logger,
                 img_formats: tuple = ('.jpg',),
                 resolution: float = 100.0):

        self.result_file: Path = Path(result_file)
        if not self.result_file.is_absolute():
            self.result_file = Path(os.getcwd(), self.result_file)

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
            return

        result_pdf = Path(result_pdf) if result_pdf else self.result_file
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
        self.logger.info(f'Created pdf {result_pdf} from {folder} ({time.time() - start} sec)')

    def merge_pdfs(self, *pdfs: Path, result_pdf: Path = None):
        result_pdf = result_pdf if result_pdf else self.result_file
        pdf_merger = PdfMerger()
        try:
            for pdf_path in pdfs:
                pdf_merger.append(pdf_path)

            with open(result_pdf, 'wb') as f:
                pdf_merger.write(f)
        except Exception:
            raise
        finally:
            pdf_merger.close()

    def merge(self, force: bool = False, delete_temp: bool = True):
        start = time.time()

        temp_folder: Path = self.base_folder.parent / self.TEMPORARY_FOLDER_NAME
        chapters_temp = temp_folder / 'chapters_pdfs'

        if force and chapters_temp.exists():
            shutil.rmtree(chapters_temp)

        try:
            self.convert_images_in_folder_to_pdf(self.base_folder, result_pdf=chapters_temp / '0.pdf')
            chapters_folders = []
            for f in sorted(os.listdir(self.base_folder), key=lambda p: int(Path(p).name)):
                f: Path = self.base_folder / f
                if f.is_dir():
                    chapters_folders.append(f)

            for i, folder_path in enumerate(chapters_folders, start=1):
                self.convert_images_in_folder_to_pdf(folder=folder_path, result_pdf=chapters_temp / f'{i}.pdf')

            self.merge_pdfs(*(chapters_temp / f for f in os.listdir(chapters_temp)))

        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if delete_temp:
                self.logger.debug(f'Deleting temp: {temp_folder}')
                shutil.rmtree(temp_folder)

        self.logger.info(f'Finished within {round(time.time() - start, 2)} sec')
        self.logger.info(f'Result stored in {self.result_file}')


from typing import List
from PIL import Image
import os
import time
from PyPDF2 import PdfMerger
from pathlib import Path
import shutil


class PDFMerger:
    def __init__(self, result_file: Path, data_folder: Path, img_formats: tuple = ('.jpg',)):
        # upper point of walk
        self.result_file: Path = Path(result_file)
        if not self.result_file.is_absolute():
            self.result_file = Path(os.getcwd(), self.result_file)
        self.base_folder: Path = Path(data_folder)
        self.img_formats = img_formats

    def get_collected_images(self) -> List[Path]:
        collected_paths = []
        for dirpath, dirnames, filenames in os.walk(self.base_folder):
            for file in filenames:
                if Path(file).suffix in self.img_formats:
                    collected_paths.append(Path(dirpath, file))

        return collected_paths

    def sort_function(self, file_path: Path) -> int:
        return int(file_path.parent.name) * 1000 + int(file_path.name.replace(file_path.suffix, ''))

    def merge(self):
        pdf_merger = PdfMerger()
        images = self.get_collected_images()
        images = list(map(str, sorted(images, key=self.sort_function)))

        temp_folder = self.base_folder.parent / 'temp'
        if temp_folder.exists():
            shutil.rmtree(temp_folder)
        temp_folder.mkdir()

        start = time.time()
        try:
            for i, image_path in enumerate(images, start=1):
                image_path = Path(image_path)
                image = Image.open(image_path)
                image_pdf = image.convert('RGB')

                temp_path = temp_folder / f'{image_path.parent.name}_{image_path.name}.pdf'

                with open(temp_path, 'wb') as f:
                    image_pdf.save(f, "PDF", resolution=100.0)

                print('Converted', temp_path, 'to pdf', f'{i}/{len(images)}')

                pdf_merger.append(temp_path)

            with open(self.result_file, 'wb') as f:
                pdf_merger.write(f)

        except Exception as e:
            print(e)
            raise e

        pdf_merger.close()
        del pdf_merger
        shutil.rmtree(temp_folder)
        print(f'Finished within {round(time.time() - start, 2)} sec')


if __name__ == '__main__':
    merger = PDFMerger('result_final.pdf', Path(__file__).parent / 'data')
    merger.merge()

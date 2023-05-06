# manga.in.ua parses


## Використання з командного рядка

```
Обов'язкові аргументи:
    --manga_url, -url       URL до потрібної манги. Приклад: boyovik/2252-berserk-berserk.html

Необов'язкові аргументи:
    --result_folder         Папка в якій зберігати pdf томів.
    --base_url              Базове url, лінка сайту. За замовчування: https://manga.in.ua
    --data_folder -d        Папка куди зберігати завантажені картинки.
    
    --join_every            Об'єднати кожні N частин в одну. Якщо 10, то 1-10.pdf, 11-20.pdf ...
    --result_pdf -pdf       Де зберігти всі томи в один файл. Приклад: result.pdf
    --one_file *            Об'єднати всі томи в один файл. 
    
    --keep_temp *           Keep temp folder.
    --keep_data *           Keep folder with downloaded images.
    
    --force *               Delete folder if exists 
    --resolution, -r,       PDF resolution. За замовчування: 100.0
    --log_level             Log level. За замовчування: 20.

* - flag

Приклад:
parser.py -url boyovik/2252-berserk-berserk.html

```

## CLI usage
```

Required arguments:
    --manga_url, -url       Needed manga url*. Example: boyovik/2252-berserk-berserk.html

Optional arguments:
    --result_folder         The path where to store the result chapters pdfs.
    --base_url              Base url. By default: https://manga.in.ua
    --data_folder -d        The path where to store downloaded images
    
    --join_every            Join every N chapters in one. If 10, then 1-10.pdf, 11-20.pdf ...
    --result_pdf -pdf       The path where to store the result pdf.
    --one_file *            Merge all manga in single pdf.
    
    --keep_temp *           Keep temp folder.
    --keep_data *           Keep folder with downloaded images.
    
    --force *               Delete folder if exists 
    --resolution, -r,       PDF resolution. By default: 100.0
    --log_level             Log level. By defalut: 20.

* - flag

Example:
parser.py -url boyovik/2252-berserk-berserk.html
```
### Speed test:

| URL                                              | Chapters |  Time   | Imgs format |
|--------------------------------------------------|:--------:|:-------:|:-----------:|
| boyovik/2252-berserk-berserk.html                |   379    |   31m   |     jpg     |
| boyovik/15-ataka-titaniv-shingeki-no-kyojin.html |    82    | 1h 37 m |    webp     |
| boyovik/49-velikij-kush-one-piece.html           |   227    |  25 m   |  jpg, png   |

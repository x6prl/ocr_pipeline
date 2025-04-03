import os
import logging
from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)
from PIL import Image, UnidentifiedImageError
import shutil # For testing block cleanup

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
SUPPORTED_PDF_EXT = {'.pdf'}

def iterate_document_items(input_dir_abs: str, config: dict):
    """
    Генератор, обходящий input_dir_abs, находящий поддерживаемые файлы
    (изображения и PDF) и возвращающий (yields) для каждой страницы/изображения
    кортеж (metadata, pil_image). Обрабатывает PDF постранично.

    Args:
        input_dir_abs (str): Абсолютный путь к директории с входными файлами.
        config (dict): Словарь конфигурации.

    Yields:
        tuple: Кортеж вида (dict, PIL.Image.Image), где dict - метаданные,
               а PIL.Image.Image - изображение. Либо (None, None) при ошибке.
    """
    pdf_dpi = config.get('pdf_dpi', 300)
    # Получаем только имя базовой входной директории для метаданных
    input_dir_base_name = os.path.basename(input_dir_abs.rstrip('/\\')) # Удаляем слэш в конце, если есть

    logger.info(f"Сканирование директории: {input_dir_abs}")
    logger.debug(f"Имя базовой директории для метаданных: '{input_dir_base_name}'")
    logger.debug(f"Поддерживаемые форматы изображений: {SUPPORTED_IMAGE_EXT}")
    logger.debug(f"Поддерживаемые форматы документов: {SUPPORTED_PDF_EXT}")
    logger.debug(f"DPI для конвертации PDF: {pdf_dpi}")

    found_files_count = 0
    processed_items_count = 0

    try:
        # Рекурсивный обход, если нужны файлы в поддиректориях
        for root, _, files in os.walk(input_dir_abs):
            for item_name in files:
                file_path = os.path.join(root, item_name)
                _, file_extension = os.path.splitext(item_name.lower())

                # Вычисляем относительный путь от input_dir_abs
                try:
                    relative_path = os.path.relpath(file_path, start=input_dir_abs)
                except ValueError as e:
                    # Может возникнуть, если пути на разных дисках (Windows)
                    logger.error(f"Не удалось вычислить относительный путь для {file_path} от {input_dir_abs}: {e}")
                    relative_path = item_name # В крайнем случае используем просто имя файла

                # --- Обработка изображений ---
                if file_extension in SUPPORTED_IMAGE_EXT:
                    found_files_count += 1
                    logger.debug(f"Найдено изображение: '{relative_path}'")
                    try:
                        img = Image.open(file_path)
                        img.load() # Загружаем данные изображения
                        metadata = {
                            'input_directory': input_dir_base_name, # Базовая папка
                            'relative_path': relative_path,        # Путь отн. базовой
                            'original_filename': item_name,        # Имя файла
                            'source_path': file_path,              # Полный путь (для логов/отладки)
                            'source_type': 'image',                # Тип источника
                            'page_num': 1                          # Условно 1 страница
                        }
                        processed_items_count += 1
                        yield metadata, img.copy() # Возвращаем копию
                        img.close() # Закрываем файл
                    except UnidentifiedImageError:
                        logger.error(f"Не удалось распознать формат изображения: {file_path}")
                        yield None, None
                    except Exception as e:
                        logger.error(f"Ошибка при чтении изображения {file_path}: {e}", exc_info=True)
                        yield None, None

                # --- Обработка PDF (ПОСТРАНИЧНО) ---
                elif file_extension in SUPPORTED_PDF_EXT:
                    found_files_count += 1
                    logger.debug(f"Найден PDF: '{relative_path}'")
                    total_pages = 0
                    try:
                        # 1. Получаем общее количество страниц
                        # (указываем poppler_path=None, т.к. pdf2image обычно сам находит его в PATH)
                        info = pdfinfo_from_path(file_path, userpw=None, poppler_path=None)
                        total_pages = info.get("Pages", 0)
                        if total_pages <= 0:
                            logger.warning(f"PDF файл '{relative_path}' не содержит страниц или не удалось определить их количество.")
                            continue # Пропускаем этот файл, нет смысла обрабатывать

                        logger.info(f"Обработка PDF: '{relative_path}' (Всего страниц: {total_pages})")

                        # 2. Цикл по страницам
                        for page_num in range(1, total_pages + 1):
                            logger.info(f"Конвертация страницы {page_num} из {total_pages} файла '{relative_path}'...")
                            page_img = None # Для корректной очистки в finally
                            try:
                                # 3. Конвертируем ТОЛЬКО ОДНУ страницу
                                images = convert_from_path(
                                    file_path,
                                    dpi=pdf_dpi,
                                    poppler_path=None,
                                    first_page=page_num,
                                    last_page=page_num # Указываем первую и последнюю страницу как одну и ту же
                                )

                                if images:
                                    page_img = images[0] # Получаем единственное изображение из списка
                                    metadata = {
                                        'input_directory': input_dir_base_name,
                                        'relative_path': relative_path,
                                        'original_filename': item_name,
                                        'source_path': file_path,
                                        'source_type': 'pdf_page',
                                        'page_num': page_num
                                    }
                                    processed_items_count += 1
                                    # 4. Возвращаем результат для текущей страницы НЕМЕДЛЕННО
                                    yield metadata, page_img
                                    # Очистка изображения будет происходить в вызывающем коде (main.py)
                                else:
                                    logger.warning(f"Не удалось конвертировать страницу {page_num} из '{relative_path}' (получен пустой список).")
                                    yield None, None # Сигнал об ошибке для этой страницы

                            except Exception as page_err:
                                # Ошибка при конвертации КОНКРЕТНОЙ страницы
                                logger.error(f"Ошибка при конвертации страницы {page_num} файла '{relative_path}': {page_err}", exc_info=True)
                                # Сигнализируем об ошибке для этой конкретной страницы
                                yield None, None

                    except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError) as info_err:
                        # Ошибка при получении ИНФОРМАЦИИ о файле (до цикла по страницам)
                        logger.error(f"Критическая ошибка при получении информации о PDF '{relative_path}': {info_err}. Файл пропущен.", exc_info=True)
                        yield None, None # Сигнал об ошибке для всего этого PDF
                    except FileNotFoundError:
                         logger.error(f"Файл не найден при обработке PDF: {file_path}")
                         yield None, None
                    except Exception as e:
                         # Любая другая ошибка на уровне файла PDF
                        logger.error(f"Непредвиденная ошибка при обработке PDF '{relative_path}': {e}", exc_info=True)
                        yield None, None

                # --- Неподдерживаемые файлы ---
                # Логирование пропущенных файлов отключено по умолчанию, чтобы избежать спама
                # else:
                #    logger.debug(f"Пропущен неподдерживаемый файл: {relative_path}")

    except FileNotFoundError:
        logger.error(f"Входная директория не найдена при сканировании: {input_dir_abs}")
    except Exception as e:
        logger.error(f"Ошибка при сканировании директории {input_dir_abs}: {e}", exc_info=True)

    logger.info(f"Сканирование завершено. Найдено поддерживаемых файлов: {found_files_count}. Обработано элементов (страниц/изображений): {processed_items_count}")


# --- Тестовый блок ---
if __name__ == '__main__':
    # Создадим временные директории и файлы для теста
    script_dir = os.path.dirname(__file__) or '.'
    test_input_dir = os.path.join(script_dir, '../', 'temp_test_input_fh')
    if os.path.exists(test_input_dir):
        shutil.rmtree(test_input_dir)
    os.makedirs(test_input_dir)

    # Поддиректория для теста рекурсии
    sub_dir = os.path.join(test_input_dir, 'subdir')
    os.makedirs(sub_dir)

    # Настройка базового логирования для теста
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')

    # Создадим тестовые файлы
    try:
        # Изображение в корне
        img_test = Image.new('RGB', (60, 30), color='red')
        img_test_path = os.path.join(test_input_dir, 'test_image.png')
        img_test.save(img_test_path)
        print(f"Создан тестовый файл: {img_test_path}")

        # Изображение в поддиректории
        img_test_sub = Image.new('RGB', (60, 30), color='blue')
        img_test_sub_path = os.path.join(sub_dir, 'sub_image.jpg')
        img_test_sub.save(img_test_sub_path)
        print(f"Создан тестовый файл: {img_test_sub_path}")

        # Пустой текстовый файл для проверки пропуска
        txt_test_path = os.path.join(test_input_dir, 'test_skip.txt')
        with open(txt_test_path, 'w') as f:
            f.write("Этот файл нужно пропустить.")
        print(f"Создан тестовый файл: {txt_test_path}")

        # Тестовый PDF (если есть возможность создать или скопировать)
        # Для примера: создадим фиктивный PDF с помощью reportlab (нужно установить: pip install reportlab)
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            pdf_path = os.path.join(test_input_dir, 'test_doc.pdf')
            c = canvas.Canvas(pdf_path, pagesize=A4)
            c.drawString(100, 750, "Page 1 Content.")
            c.showPage()
            c.drawString(100, 750, "Page 2 Content.")
            c.showPage()
            c.save()
            print(f"Создан тестовый PDF: {pdf_path} (2 страницы)")
        except ImportError:
            print("Библиотека reportlab не установлена. Пропустите создание тестового PDF.")
            print("Для теста PDF поместите любой PDF в папку temp_test_input_fh")
        except Exception as pdf_err:
            print(f"Не удалось создать тестовый PDF: {pdf_err}")

    except Exception as e:
        print(f"Ошибка при создании тестовых файлов: {e}")

    print("\n--- Запуск iterate_document_items ---")
    # Фиктивная конфигурация для теста
    test_config = {'pdf_dpi': 72} # Низкое DPI для скорости теста

    item_count = 0
    for metadata, image_object in iterate_document_items(test_input_dir, test_config):
        if metadata and image_object:
            item_count += 1
            print(f"\n[ITEM {item_count}] ---")
            print(f"  Метаданные:")
            for key, value in metadata.items():
                print(f"    {key}: {value}")
            print(f"  Тип изображения: {type(image_object)}")
            print(f"  Размер изображения: {image_object.size}")
            # image_object.show() # Можно раскомментировать для визуальной проверки
            del image_object # Очистка
        elif metadata is None and image_object is None:
            item_count += 1
            print(f"\n[ITEM {item_count}] --- ОШИБКА ---")
            print("  Получен сигнал об ошибке обработки элемента.")
        else:
             item_count += 1
             print(f"\n[ITEM {item_count}] --- НЕОЖИДАННЫЙ РЕЗУЛЬТАТ ---")

    print("\n--- Тестирование iterate_document_items завершено ---")

    # Очистка временной директории
    try:
        shutil.rmtree(test_input_dir)
        print(f"Удалена временная директория: {test_input_dir}")
    except Exception as e:
        print(f"Не удалось удалить временную директорию {test_input_dir}: {e}")
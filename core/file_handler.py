import os
import logging
from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
SUPPORTED_PDF_EXT = {'.pdf'}

def iterate_document_items(input_dir_abs: str, config: dict):
    """
    Генератор, обходящий input_dir_abs, находящий поддерживаемые файлы
    (изображения и PDF) и возвращающий (yields) для каждой страницы/изображения
    кортеж (metadata, pil_image).

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
                        img.load() # Загружаем данные
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
                        img.close()
                    except UnidentifiedImageError:
                        logger.error(f"Не удалось распознать формат изображения: {file_path}")
                        yield None, None
                    except Exception as e:
                        logger.error(f"Ошибка при чтении изображения {file_path}: {e}", exc_info=True)
                        yield None, None

                # --- Обработка PDF ---
                elif file_extension in SUPPORTED_PDF_EXT:
                    found_files_count += 1
                    logger.debug(f"Найден PDF: '{relative_path}'")
                    try:
                        # Пытаемся получить кол-во страниц (для информации)
                        page_count_str = "?"
                        try:
                            info = pdfinfo_from_path(file_path, userpw=None, poppler_path=None)
                            page_count_str = str(info.get("Pages", "?"))
                        except Exception as info_err:
                            logger.warning(f"Не удалось получить инфо о страницах PDF '{relative_path}': {info_err}. Попытка конвертации...")

                        logger.info(f"Обработка PDF: '{relative_path}' (Страниц: {page_count_str})")
                        images = convert_from_path(file_path, dpi=pdf_dpi, poppler_path=None)

                        if not images:
                             logger.warning(f"PDF файл '{relative_path}' пуст или не удалось конвертировать страницы.")
                             continue

                        for i, img in enumerate(images):
                            page_num = i + 1
                            metadata = {
                                'input_directory': input_dir_base_name, # Базовая папка
                                'relative_path': relative_path,        # Путь отн. базовой
                                'original_filename': item_name,        # Имя файла
                                'source_path': file_path,              # Полный путь (для логов/отладки)
                                'source_type': 'pdf_page',             # Тип источника
                                'page_num': page_num                   # Номер страницы
                            }
                            processed_items_count += 1
                            yield metadata, img # PIL image
                            # img закроется сам

                    except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError) as pdf_err:
                        logger.error(f"Ошибка обработки PDF (pdf2image) '{relative_path}': {pdf_err}", exc_info=True)
                        yield None, None
                    except FileNotFoundError:
                         logger.error(f"Файл не найден при обработке PDF: {file_path}")
                         yield None, None
                    except Exception as e:
                        logger.error(f"Непредвиденная ошибка при обработке PDF '{relative_path}': {e}", exc_info=True)
                        yield None, None

                # --- Неподдерживаемые файлы ---
                # else: (Логировать каждый пропущенный файл может быть слишком шумно)
                #    logger.debug(f"Пропущен неподдерживаемый файл: {relative_path}")

    except FileNotFoundError:
        logger.error(f"Входная директория не найдена при сканировании: {input_dir_abs}")
    except Exception as e:
        logger.error(f"Ошибка при сканировании директории {input_dir_abs}: {e}", exc_info=True)

    logger.info(f"Сканирование завершено. Найдено поддерживаемых файлов: {found_files_count}. Обработано элементов (страниц/изображений): {processed_items_count}")

# --- Тестовый блок ---
if __name__ == '__main__':
     # ... (тестовый блок без изменений, но теперь метаданные будут содержать новые поля) ...
     pass
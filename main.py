import yaml
import logging
import os
import sys
import traceback
from time import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image

# --- Импорт модулей ядра ---
try:
    from utils.logger import setup_logging
    from core.file_handler import iterate_document_items
    from core.image_processor import preprocess_image
    from core.ocr_engine import extract_text
    from core.post_processor import clean_text # Используем обновленный post_processor
    from core.output_handler import save_result
except ImportError as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать модуль ядра: {e}", file=sys.stderr)
    print("Пожалуйста, убедитесь, что все файлы (.py) находятся в правильных директориях (core/, utils/) и не содержат синтаксических ошибок.", file=sys.stderr)
    sys.exit(1)

# --- Константы ---
CONFIG_FILE = 'config.yaml'
logger = logging.getLogger('main')

# --- Функции ---

def load_config(config_path: str) -> Dict[str, Any]:
    """ Загружает конфигурацию из YAML файла. """
    logger.info(f"Загрузка конфигурации из файла: {config_path}")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if config is None:
            logger.critical(f"Конфигурационный файл '{config_path}' пуст или некорректен.")
            sys.exit(1)
        logger.info(f"Конфигурация успешно загружена.")
        return config
    except FileNotFoundError:
        logger.critical(f"Конфигурационный файл '{config_path}' не найден.")
        sys.exit(1)
    # ... (остальные except блоки без изменений) ...
    except yaml.YAMLError as e:
        logger.critical(f"Ошибка парсинга YAML в файле '{config_path}': {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Непредвиденная ошибка при загрузке конфигурации '{config_path}': {e}", exc_info=True)
        sys.exit(1)


def process_single_item(metadata: dict, image_object: Image.Image, config: dict, output_dir_abs: str) -> Tuple[bool, float]:
    """ Полный цикл обработки одного элемента. """
    item_start_time = time()
    log_prefix = f"[{metadata.get('original_filename', 'N/A')} | Page {metadata.get('page_num', 'N/A')}]" # Используем original_filename для лога
    logger.info(f"{log_prefix} Обработка элемента начата (Источник: '{metadata.get('relative_path', '?')}')")
    success_flag = False
    duration = 0.0

    try:
        # --- 1. Предобработка ---
        preproc_config = config.get('preprocessing', {})
        processed_image_np = preprocess_image(image_object, preproc_config)
        if processed_image_np is None:
            raise ValueError("Preprocessing failed")
        logger.debug(f"{log_prefix} Предобработка завершена.")

        # --- 2. OCR ---
        ocr_specific_config = {
            'lang': config.get('ocr_language', 'rus'),
            'tessdata_dir': config.get('tessdata_dir'),
            'tesseract_cmd': config.get('tesseract_cmd'),
            'ocr_config': config.get('ocr_config', '')
        }
        raw_text = extract_text(processed_image_np, ocr_specific_config)
        del processed_image_np
        if raw_text is None:
            raise ValueError("OCR failed")
        logger.debug(f"{log_prefix} OCR завершен, длина текста: {len(raw_text)}.")

        # --- 3. Постобработка ---
        # Используем обновленный post_processor для лучшей читаемости
        postproc_config = config.get('postprocessing', {})
        cleaned_text = clean_text(raw_text, postproc_config)
        logger.debug(f"{log_prefix} Постобработка завершена, итоговая длина: {len(cleaned_text)}.")
        del raw_text

        # --- 4. Формирование данных для JSON и сохранение ---
        duration = time() - item_start_time # Текущая длительность

        # Используем новую структуру JSON
        output_data = {
            "document_info": {
                "input_directory": metadata.get('input_directory'), # Из file_handler
                "relative_path": metadata.get('relative_path'),     # Из file_handler
                "original_filename": metadata.get('original_filename'),# Из file_handler
                "source_type": metadata.get('source_type'),         # Из file_handler
                "page_number": metadata.get('page_num'),            # Из file_handler
            },
            "processing_info": {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                "duration_sec": round(duration, 2),
                "ocr_engine_lang": ocr_specific_config.get('lang', 'N/A'),
                "tesseract_config_used": ocr_specific_config.get('ocr_config', 'N/A'),
            },
            "content": {
                "text": cleaned_text # Здесь лежит очищенный текст с \n
            }
        }

        # Вызов save_result не меняется
        save_success = save_result(
            data_to_save=output_data,
            output_dir_abs=output_dir_abs,
            original_filename=metadata.get('original_filename', 'unknown'),
            page_num=metadata.get('page_num', 0),
            config=config
        )

        if not save_success:
            raise ValueError("Saving failed")

        success_flag = True
        duration = time() - item_start_time
        logger.info(f"{log_prefix} Элемент успешно обработан и сохранен за {duration:.2f} сек.")

    except Exception as e:
        success_flag = False
        duration = time() - item_start_time
        logger.error(f"{log_prefix} Не удалось обработать элемент (ошибка: {type(e).__name__}). Время до ошибки: {duration:.2f} сек.")

    return success_flag, duration


def main():
    """ Основная функция оркестратора OCR конвейера. """
    script_start_time = time()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    config = load_config(CONFIG_FILE)

    try:
        setup_logging(config)
    except Exception as e:
        logger.error(f"Не удалось настроить логирование из конфигурации: {e}", exc_info=True)
        logger.warning("Продолжение работы с базовой конфигурацией логирования.")

    logger.info("="*30 + " Запуск OCR Pipeline " + "="*30)
    logger.info(f"PID процесса: {os.getpid()}")

    input_dir = config.get('input_dir', 'input_data')
    output_dir = config.get('output_dir', 'output_data')
    base_path = os.path.dirname(os.path.abspath(__file__))
    input_dir_abs = os.path.join(base_path, input_dir)
    output_dir_abs = os.path.join(base_path, output_dir)

    logger.info(f"Входная директория: {input_dir_abs}")
    logger.info(f"Выходная директория: {output_dir_abs}")

    # --- Проверки директорий (без изменений) ---
    if not os.path.isdir(input_dir_abs):
        logger.critical(f"Входная директория НЕ НАЙДЕНА: {input_dir_abs}")
        sys.exit(1)
    # ... (остальные проверки директорий) ...
    if not os.path.exists(output_dir_abs):
        try:
            os.makedirs(output_dir_abs)
            logger.info(f"Создана выходная директория: {output_dir_abs}")
        except OSError as e:
            logger.critical(f"Не удалось создать выходную директорию {output_dir_abs}: {e}", exc_info=True)
            sys.exit(1)
    elif not os.path.isdir(output_dir_abs):
         logger.critical(f"Путь для вывода '{output_dir_abs}' существует, но не является директорией.")
         sys.exit(1)

    processed_count = 0
    error_count = 0
    total_items_yielded = 0
    successful_item_times: List[float] = []

    logger.info(f"Начало сканирования директории '{input_dir_abs}' и обработки документов...")
    try:
        # Используем iterate_document_items, который теперь возвращает расширенные метаданные
        item_iterator = iterate_document_items(input_dir_abs, config)

        for metadata, image_object in item_iterator:
            total_items_yielded += 1

            if metadata is None or image_object is None:
                log_prefix_err = f"[{metadata.get('original_filename', 'N/A')} | Page {metadata.get('page_num', 'N/A')} (?)]" if metadata else "[Unknown Item]"
                logger.error(f"{log_prefix_err} Ошибка на этапе получения элемента (из file_handler). Элемент пропущен.")
                error_count += 1
                if image_object: del image_object
                if metadata: del metadata
                continue

            # Обработка одного элемента
            success, duration = process_single_item(metadata, image_object, config, output_dir_abs)

            if success:
                processed_count += 1
                successful_item_times.append(duration)
            else:
                error_count += 1

            # Освобождаем память
            del image_object
            del metadata

    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА во время итерации и обработки файлов: {e}", exc_info=True)
        error_count = total_items_yielded - processed_count

    # --- Завершение и статистика (без изменений от предыдущей версии) ---
    script_end_time = time()
    total_time = script_end_time - script_start_time

    logger.info("="*30 + " Завершение работы OCR Pipeline " + "="*30)
    logger.info(f"Всего элементов найдено/попытано обработать: {total_items_yielded}")
    logger.info(f"Успешно обработано и сохранено: {processed_count}")
    logger.info(f"Элементов с ошибками: {error_count}")
    logger.info(f"Общее время выполнения: {total_time:.2f} сек.")

    if total_items_yielded > 0:
        avg_time_per_item_total = total_time / total_items_yielded
        logger.info(f"Среднее время на элемент (всего попыток): {avg_time_per_item_total:.2f} сек.")
    if processed_count > 0:
        avg_time_per_item_success = sum(successful_item_times) / processed_count
        logger.info(f"Среднее время на УСПЕШНО обработанный элемент: {avg_time_per_item_success:.2f} сек.")
    elif total_items_yielded > 0:
         logger.info("Среднее время на успешный элемент: N/A (нет успешно обработанных).")
    elif os.path.exists(input_dir_abs) and any(os.scandir(input_dir_abs)):
        logger.warning("Не найдено поддерживаемых файлов для обработки во входной директории (или они не были обработаны file_handler).")
    else:
        logger.info("Входная директория пуста или не существует.")

    exit_code = 0 if processed_count > 0 or (total_items_yielded == 0 and error_count == 0) else 1
    if error_count > 0:
        logger.warning(f"Завершено с {error_count} ошибками.")
    elif processed_count == 0 and total_items_yielded > 0:
         logger.warning("Ни один элемент не был успешно обработан.")

    logger.info(f"Завершение работы с кодом выхода: {exit_code}")
    sys.exit(exit_code)

# --- Точка входа ---
if __name__ == "__main__":
    main()
import json
import logging
import os
import re
import shutil # Импортируем для использования в тестовом блоке

logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """Удаляет или заменяет недопустимые символы из имени файла."""
    if not filename:
        return 'unnamed_file'
    # Удаляем путь, оставляем только имя файла
    base_name = os.path.basename(filename)
    # Удаляем расширение
    name_part, _ = os.path.splitext(base_name)
    # Заменяем пробелы и последовательности не буквенно-цифровых символов на подчеркивание
    # Разрешаем русские буквы, цифры, дефис и подчеркивание
    # Добавляем точку в разрешенные символы на всякий случай
    sanitized_name = re.sub(r'[^\w.\-а-яА-ЯёЁ]+', '_', name_part, flags=re.UNICODE)
    # Удаляем последовательные подчеркивания
    sanitized_name = re.sub(r'_+', '_', sanitized_name)
    # Удаляем лидирующие/завершающие подчеркивания
    sanitized_name = sanitized_name.strip('_')
    # Если имя стало пустым после очистки, используем 'unnamed'
    if not sanitized_name:
        sanitized_name = 'unnamed_file'
    return sanitized_name

def save_result(data_to_save: dict,
                output_dir_abs: str,
                original_filename: str,
                page_num: int,
                config: dict) -> bool:
    """
    Сохраняет обработанные данные (словарь data_to_save) в JSON файл.
    Имя файла генерируется на основе original_filename и page_num.

    Args:
        data_to_save (dict): Словарь с данными для сохранения (в новой структуре).
        output_dir_abs (str): Абсолютный путь к директории для сохранения.
        original_filename (str): Имя исходного файла для генерации имени выходного файла.
        page_num (int): Номер страницы для генерации имени выходного файла.
        config (dict): Общий словарь конфигурации.

    Returns:
        bool: True при успехе сохранения, False при ошибке.
    """
    output_format = config.get('output_format', 'json').lower()

    if output_format != 'json':
        logger.error(f"Формат вывода '{output_format}' не поддерживается. Поддерживается только 'json'.")
        return False

    try:
        # 1. Генерируем безопасное базовое имя файла из ПЕРЕДАННОГО original_filename
        sanitized_base_name = sanitize_filename(original_filename)

        # 2. Составляем имя выходного файла
        output_filename = f"{sanitized_base_name}_page_{page_num}.{output_format}"
        output_path = os.path.join(output_dir_abs, output_filename)

        logger.info(f"Попытка сохранения результата в файл: {output_path}")

        # 3. Создаем директорию, если нужно
        os.makedirs(output_dir_abs, exist_ok=True)

        # 4. Сохраняем ПЕРЕДАННЫЕ данные data_to_save в JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2) # indent=2

        logger.info(f"Результат успешно сохранен: {output_path}")
        return True

    except (IOError, OSError) as e:
        logger.error(f"Ошибка ввода-вывода при сохранении файла {output_path}: {e}", exc_info=True)
        return False
    except TypeError as e:
        # Часто возникает, если пытаемся сериализовать неподдерживаемый тип
        logger.error(f"Ошибка типа данных при сериализации в JSON для {output_path}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при сохранении результата в {output_path}: {e}", exc_info=True)
        return False


# Пример использования
if __name__ == '__main__':
    # Настройка логирования для теста
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

    # Создаем временную директорию для теста
    script_dir = os.path.dirname(__file__) or '.'
    test_output_dir = os.path.join(script_dir, '../', 'temp_test_output_handler')
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir) # Удаляем старую, если есть
    os.makedirs(test_output_dir)
    logger.info(f"Создана временная директория для теста: {test_output_dir}")

    # --- Тест 1: Стандартные данные в новом формате ---
    logger.debug("\n--- Тест 1: Стандартный вызов ---")
    test_data_1 = {
        "metadata": {
            "source": {"filename": "Мой Док.pdf", "original_path": "/data/Мой Док.pdf", "page_number": 2},
            "processing": {"timestamp_utc": "2023-10-27T14:00:00Z", "duration_sec": 3.14, "ocr_engine_lang": "rus+eng"}
        },
        "content": {"text": "Текст стр. 2"}
    }
    test_config_1 = {'output_format': 'json'}
    # Вызываем с новой сигнатурой
    success_1 = save_result(
        data_to_save=test_data_1,
        output_dir_abs=test_output_dir,
        original_filename="Мой Док.pdf", # Имя файла для имени вывода
        page_num=2,                       # Номер страницы для имени вывода
        config=test_config_1
    )
    expected_file_1 = os.path.join(test_output_dir, 'Мой_Док_page_2.json')
    logger.info(f"Результат теста 1: {success_1}. Ожидаемый файл: {expected_file_1}")
    assert success_1 and os.path.exists(expected_file_1), "Тест 1 провален!"
    logger.debug("Тест 1 пройден.")


    # --- Тест 2: Нестандартное имя файла ---
    logger.debug("\n--- Тест 2: Имя файла с недопустимыми символами ---")
    test_data_2 = {
        "metadata": {"source": {"filename": 'файл*с/\\символами?.png'}, "page_number": 1},
        "content": {"text": "PNG text"}
    }
    test_config_2 = {'output_format': 'json'}
    success_2 = save_result(
        data_to_save=test_data_2,
        output_dir_abs=test_output_dir,
        original_filename='файл*с/\\символами?.png', # Оригинальное имя
        page_num=1,
        config=test_config_2
    )
    expected_file_2 = os.path.join(test_output_dir, 'файл_с_символами_page_1.json')
    logger.info(f"Результат теста 2: {success_2}. Ожидаемый файл: {expected_file_2}")
    assert success_2 and os.path.exists(expected_file_2), "Тест 2 провален!"
    logger.debug("Тест 2 пройден.")

    logger.info(f"\nПроверьте содержимое директории: {test_output_dir}")
    # Можно раскомментировать удаление, если директория больше не нужна
    # shutil.rmtree(test_output_dir)
    # logger.info(f"Временная директория удалена: {test_output_dir}")
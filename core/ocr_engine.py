import logging
import pytesseract
import numpy as np
from PIL import Image # Только для type hinting и возможной отладки

logger = logging.getLogger(__name__)

def extract_text(image_array: np.ndarray, config: dict) -> str | None:
    """
    Извлекает текст из изображения с использованием Tesseract OCR.

    Args:
        image_array (np.ndarray): Изображение в формате NumPy array
                                  (предпочтительно Grayscale или BGR,
                                  как возвращает image_processor).
        config (dict): Словарь с настройками OCR. Должен содержать ключи:
                       'lang' (str): Язык(и) Tesseract (e.g., 'rus', 'eng', 'rus+eng').
                       'tesseract_cmd' (str | None): Путь к исполняемому файлу tesseract.
                                                    None - если tesseract в PATH.
                       'tessdata_dir' (str | None): Путь к директории tessdata.
                                                   None - использовать стандартную.
                       'ocr_config' (str): Дополнительные параметры для Tesseract
                                          (e.g., '--psm 3 --oem 1').

    Returns:
        str | None: Распознанный текст или None в случае ошибки.
    """
    logger.info("Запуск OCR...")

    # 1. Получаем параметры из конфига
    lang = config.get('lang', 'rus')
    tesseract_cmd = config.get('tesseract_cmd')
    tessdata_dir = config.get('tessdata_dir')
    ocr_config_str = config.get('ocr_config', '').strip()

    # 2. Устанавливаем путь к tesseract, если он указан
    if tesseract_cmd:
        logger.debug(f"Указан путь к Tesseract: {tesseract_cmd}")
        # Эта строка изменяет глобальную переменную в pytesseract для этого сеанса Python
        # Делать это можно, но если вы планируете многопоточность,
        # будьте осторожны или передавайте путь в саму функцию tesseract через параметры,
        # если такая возможность появится в будущем в pytesseract.
        # Сейчас стандартный способ - через эту команду.
        try:
            # Проверяем, отличается ли он от текущего, чтобы не вызывать лишний раз
            if pytesseract.pytesseract.tesseract_cmd != tesseract_cmd:
                 pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        except AttributeError:
             logger.error("Не удалось установить tesseract_cmd. Возможно, старая версия pytesseract?")
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при установке tesseract_cmd: {e}")


    # 3. Собираем строку конфигурации для Tesseract
    custom_config = ocr_config_str
    if tessdata_dir:
        # Добавляем параметр --tessdata-dir, если он еще не задан в ocr_config_str
        if '--tessdata-dir' not in custom_config:
            custom_config = f'--tessdata-dir "{tessdata_dir}" {custom_config}'.strip()
            logger.debug(f"Используется кастомная директория tessdata: {tessdata_dir}")
        else:
             logger.warning(f"--tessdata-dir указан и в 'tessdata_dir', и в 'ocr_config'. Используется значение из 'ocr_config': {custom_config}")

    logger.info(f"Параметры OCR: Язык='{lang}', Конфиг='{custom_config}'")

    # 4. Выполняем OCR
    try:
        # Конвертируем NumPy array обратно в PIL Image формат,
        # т.к. pytesseract часто лучше работает с ним напрямую
        # Или убедимся что наш NumPy array правильного формата
        if image_array is None:
            logger.error("Получено пустое изображение (None) для OCR.")
            return None

        # Проверка типа данных, Tesseract обычно ожидает uint8
        if image_array.dtype != np.uint8:
            logger.warning(f"Тип данных изображения ({image_array.dtype}) не uint8. Попытка конвертации...")
            try:
                # Нормализация если нужно (например, если пришли float 0-1)
                if image_array.max() <= 1.0 and image_array.min() >= 0:
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    # Простое приведение типа, может привести к потере данных, если диапазон не 0-255
                    image_array = image_array.astype(np.uint8)
            except Exception as conv_err:
                logger.error(f"Ошибка конвертации типа данных изображения в uint8: {conv_err}. OCR может не сработать.")
                return None

        # --- Основной вызов pytesseract ---
        # Передаем NumPy array напрямую (pytesseract умеет с ними работать)
        extracted_text = pytesseract.image_to_string(
            image_array,
            lang=lang,
            config=custom_config
        )

        logger.info(f"OCR успешно завершен. Извлечено символов: {len(extracted_text)}")
        # Логируем только начало текста для отладки
        logger.debug(f"Начало извлеченного текста:\n---\n{extracted_text[:200]}\n---")

        return extracted_text

    except pytesseract.TesseractNotFoundError:
        logger.critical(
            "ОШИБКА: Tesseract не найден. Убедитесь, что он установлен и "
            "путь к нему прописан в системной переменной PATH или в 'tesseract_cmd' в config.yaml."
        )
        # После такой ошибки продолжать бессмысленно, хорошо бы остановить весь процесс.
        # Можно бросить исключение выше, чтобы main.py его поймал и завершился.
        # Например: raise pytesseract.TesseractNotFoundError
        # Но пока просто вернем None, чтобы обработать как ошибку элемента.
        return None
    except pytesseract.TesseractError as e:
        logger.error(f"Ошибка во время выполнения Tesseract: {e}", exc_info=True)
        # Эта ошибка может возникать из-за проблем с языковыми данными, параметрами и т.д.
        return None
    except Exception as e:
        logger.error(f"Непредвиденная ошибка во время OCR: {e}", exc_info=True)
        return None


# Пример использования (только для демонстрации вызова, нужен NumPy array)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Тест 1: Создание фейкового изображения и базовый вызов ---
    print("\n--- Тест 1: Базовый вызов с фейковым изображением ---")
    # Создаем простое черное изображение с белым текстом (нужен OpenCV для этого)
    try:
        import cv2
        fake_image = np.zeros((100, 400), dtype=np.uint8) # Grayscale
        cv2.putText(fake_image, "Test OCR 123", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2)
        # cv2.imshow("Fake Image", fake_image)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
    except ImportError:
        print("OpenCV не установлен, создаем просто белое изображение.")
        fake_image = np.full((100, 400), 255, dtype=np.uint8) # Белое изображение

    test_config_1 = {
        'lang': 'eng', # Используем 'eng' для простоты теста, если русский не установлен
        'tesseract_cmd': None,
        'tessdata_dir': None,
        'ocr_config': '--psm 6' # Assume a single uniform block of text.
    }

    result_text_1 = extract_text(fake_image, test_config_1)

    if result_text_1 is not None:
        print(f"Тест 1 Результат:\n---\n{result_text_1}\n---")
    else:
        print("Тест 1 не удался (проверьте установку Tesseract и английского языка).")


    # --- Тест 2: Вызов с указанием несуществующего языка (ожидается ошибка) ---
    print("\n--- Тест 2: Вызов с неверным языком ---")
    test_config_2 = {
        'lang': 'invalid_lang_code', # Несуществующий язык
        'tesseract_cmd': None,
        'tessdata_dir': None,
        'ocr_config': '--psm 3'
    }
    result_text_2 = extract_text(fake_image, test_config_2)
    if result_text_2 is None:
        print("Тест 2 успешно показал ошибку (вернул None), как и ожидалось.")
    else:
        print(f"Тест 2 неожиданно вернул текст:\n---\n{result_text_2}\n---")
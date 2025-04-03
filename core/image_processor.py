import logging
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

def preprocess_image(pil_image: Image.Image, config: dict) -> np.ndarray | None:
    """
    Выполняет предобработку изображения для OCR с использованием OpenCV.

    Args:
        pil_image (PIL.Image.Image): Входное изображение в формате PIL.
        config (dict): Словарь с настройками предобработки из секции 'preprocessing'.
                       Пример: {'enabled': True, 'grayscale': True, 'deskew': True,
                                'binarization_method': 'otsu', 'noise_removal': 'median_3'}

    Returns:
        np.ndarray | None: Обработанное изображение в формате NumPy array (OpenCV BGR или Grayscale),
                         готовое для Tesseract. Возвращает None в случае ошибки.
    """
    if not config.get('enabled', False):
        logger.info("Предобработка отключена в конфигурации.")
        # Конвертируем PIL Image в OpenCV BGR формат (стандартный для OpenCV)
        try:
            open_cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return open_cv_image
        except Exception as e:
            logger.error(f"Ошибка конвертации PIL Image в OpenCV: {e}", exc_info=True)
            return None

    logger.info("Начало предобработки изображения...")
    try:
        # 1. Конвертация PIL Image в OpenCV формат (NumPy array BGR)
        # PIL использует RGB, OpenCV использует BGR
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        working_image = img.copy() # Работаем с копией

        # 2. Преобразование в оттенки серого (Grayscale)
        # Многие операции (deskew, binarization) и сам Tesseract лучше работают с grayscale
        use_grayscale = config.get('grayscale', True) # По умолчанию используем grayscale
        gray = None
        if use_grayscale or config.get('deskew') or config.get('binarization_method'):
            try:
                gray = cv2.cvtColor(working_image, cv2.COLOR_BGR2GRAY)
                working_image = gray # Далее работаем с grayscale, если оно нужно
                logger.debug("Изображение преобразовано в оттенки серого.")
            except cv2.error as e:
                logger.warning(f"Не удалось преобразовать в оттенки серого: {e}. Продолжаем с BGR.")
                # Если не удалось, но grayscale требовался для других шагов, может быть проблема
                # Но лучше попытаться продолжить, чем упасть
                gray = None # Явно указываем, что grayscale не доступен


        # 3. Коррекция наклона (Deskew)
        if config.get('deskew', False) and gray is not None: # Deskew требует grayscale
            logger.debug("Применение коррекции наклона (deskew)...")
            try:
                # Используем инвертированную бинаризацию Оцу для выделения текста
                thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

                # Находим координаты всех пикселей текста
                coords = np.column_stack(np.where(thresh > 0))

                if coords.shape[0] < 5: # Проверка, что есть достаточно точек для minAreaRect
                    logger.warning("Недостаточно точек для определения угла наклона. Пропуск deskew.")
                else:
                     # Находим минимальный ограничивающий прямоугольник
                    rect = cv2.minAreaRect(coords)
                    angle = rect[-1] # Угол в диапазоне [-90, 0)

                    # Корректируем угол для функции вращения
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle

                    logger.info(f"Обнаружен угол наклона: {angle:.2f} градусов.")

                    # Вращаем изображение для компенсации наклона
                    # Tesseract лучше справляется с небольшим наклоном, поэтому вращаем только если угол значителен
                    if abs(angle) > 0.5 and abs(angle) < 45: # Порог для вращения (можно сделать настраиваемым)
                         (h, w) = working_image.shape[:2] # Используем размеры working_image (может быть gray или BGR)
                         center = (w // 2, h // 2)
                         M = cv2.getRotationMatrix2D(center, angle, 1.0)

                         # Вращаем working_image (может быть gray или BGR)
                         # Используем белую рамку, т.к. часто фон белый
                         working_image = cv2.warpAffine(working_image, M, (w, h),
                                                      flags=cv2.INTER_CUBIC, # Качественная интерполяция
                                                      borderMode=cv2.BORDER_CONSTANT,
                                                      borderValue=(255, 255, 255) if len(working_image.shape) == 3 else 255) # Белая граница
                         logger.debug(f"Изображение повернуто на {-angle:.2f} градусов.")
                         # Если вращали цветное изображение, надо обновить и grayscale версию, если она была
                         if len(working_image.shape) == 3 and use_grayscale:
                             gray = cv2.cvtColor(working_image, cv2.COLOR_BGR2GRAY)
                    else:
                        logger.debug(f"Угол наклона ({angle:.2f}) слишком мал или велик, вращение пропущено.")


            except Exception as e:
                 logger.error(f"Ошибка во время коррекции наклона: {e}", exc_info=True)
                 # Продолжаем без deskew

        # --- Tesseract 4+ обычно лучше работает с grayscale, чем с бинаризованными ---
        # --- Оставляем бинаризацию как опцию, но по умолчанию не используем ---

        # 4. Бинаризация (Преобразование в ч/б)
        binarization_method = config.get('binarization_method', None)
        if binarization_method and gray is not None: # Требует grayscale
             logger.debug(f"Применение бинаризации (метод: {binarization_method})...")
             try:
                if binarization_method == 'otsu':
                     # Глобальная бинаризация Оцу
                     _, working_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                     logger.debug("Применена бинаризация Оцу.")
                elif binarization_method == 'adaptive':
                     # Адаптивная бинаризация (хорошо для неравномерного освещения)
                     block_size = config.get('adaptive_thresh_block_size', 11) # Должен быть нечетным
                     c_value = config.get('adaptive_thresh_C', 2)
                     working_image = cv2.adaptiveThreshold(gray, 255,
                                                           cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                           cv2.THRESH_BINARY,
                                                           block_size, c_value)
                     logger.debug(f"Применена адаптивная бинаризация (block: {block_size}, C: {c_value}).")
                else:
                     logger.warning(f"Неизвестный метод бинаризации: {binarization_method}. Бинаризация пропущена.")
                     # Если метод неизвестен, working_image остается grayscale (или BGR, если grayscale не удался)
             except Exception as e:
                logger.error(f"Ошибка во время бинаризации: {e}", exc_info=True)
                # Продолжаем с тем, что было до бинаризации

        elif binarization_method and gray is None:
             logger.warning("Бинаризация пропущена, так как не удалось получить grayscale изображение.")


        # 5. Удаление шума
        noise_method = config.get('noise_removal', None)
        if noise_method:
            logger.debug(f"Применение удаления шума (метод: {noise_method})...")
            try:
                if noise_method.startswith('median_'):
                    kernel_size_str = noise_method.split('_')[-1]
                    kernel_size = int(kernel_size_str)
                    if kernel_size % 2 == 1: # Медианный фильтр требует нечетный размер ядра
                        working_image = cv2.medianBlur(working_image, kernel_size)
                        logger.debug(f"Применен Median Blur с ядром {kernel_size}x{kernel_size}.")
                    else:
                         logger.warning(f"Размер ядра для Median Blur должен быть нечетным, получен {kernel_size}. Шум не удален.")
                else:
                    logger.warning(f"Неизвестный метод удаления шума: {noise_method}. Пропущено.")
            except ValueError:
                 logger.warning(f"Некорректный размер ядра в 'noise_removal': {noise_method}. Пропущено.")
            except Exception as e:
                 logger.error(f"Ошибка при удалении шума: {e}", exc_info=True)

        # --- Финальное изображение для Tesseract ---
        # Tesseract обычно лучше работает с Grayscale или BGR.
        # Если была бинаризация, working_image уже ч/б (2D).
        # Если не было бинаризации, working_image - это grayscale (2D) или BGR (3D).
        # Предпочтительно передавать grayscale, если он доступен и бинаризации не было.
        if binarization_method is None and gray is not None and len(working_image.shape) == 3:
             # Если бинаризации не было, и есть grayscale, и working_image все еще BGR
             # (значит, grayscale использовался только для deskew, но не для конечного результата)
             # То вернем grayscale, если он был разрешен изначально.
             if use_grayscale:
                 logger.debug("Возвращаем grayscale изображение для OCR.")
                 final_image = gray
             else:
                 logger.debug("Возвращаем BGR изображение для OCR (grayscale не был включен в конфиге).")
                 final_image = working_image # Который BGR после deskew
        else:
             # Либо была бинаризация (working_image ч/б 2D)
             # Либо не было бинаризации, но working_image уже grayscale (2D)
             # Либо grayscale получить не удалось (working_image BGR 3D)
             logger.debug(f"Возвращаем изображение с формой {working_image.shape} для OCR.")
             final_image = working_image


        logger.info(f"Предобработка завершена. Форма итогового изображения: {final_image.shape}")
        return final_image

    except Exception as e:
        logger.error(f"Критическая ошибка на этапе предобработки: {e}", exc_info=True)
        return None


# Пример использования (можно запустить этот файл напрямую для теста)
if __name__ == '__main__':
    # Настройка базового логирования для теста
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Создадим тестовое изображение PIL
    test_pil_image = Image.new('RGB', (400, 100), color='lightgray')
    # Можно добавить текст для теста deskew, но для простоты оставим так
    print("Создано тестовое PIL изображение.")

    # --- Тест 1: Предобработка включена (Grayscale + Deskew) ---
    print("\n--- Тест 1: Grayscale + Deskew ---")
    test_config_1 = {
        'enabled': True,
        'grayscale': True,
        'deskew': True, # На пустом сером изображении угол будет 0 или случайный, но код выполнится
        'binarization_method': None,
        'noise_removal': None
    }
    processed_img_1 = preprocess_image(test_pil_image, test_config_1)
    if processed_img_1 is not None:
        print(f"Тест 1 завершен. Форма итогового изображения: {processed_img_1.shape}, Тип данных: {processed_img_1.dtype}")
        # cv2.imshow("Processed 1", processed_img_1) # Раскомментируйте для просмотра
        # cv2.waitKey(0)
    else:
        print("Тест 1 не удался.")

    # --- Тест 2: Предобработка включена (Otsu Binarization + Median Noise Removal) ---
    print("\n--- Тест 2: Otsu + Median_3 ---")
    test_config_2 = {
        'enabled': True,
        'grayscale': True, # Бинаризация требует grayscale
        'deskew': False,
        'binarization_method': 'otsu',
        'noise_removal': 'median_3'
    }
    processed_img_2 = preprocess_image(test_pil_image, test_config_2)
    if processed_img_2 is not None:
        print(f"Тест 2 завершен. Форма итогового изображения: {processed_img_2.shape}, Тип данных: {processed_img_2.dtype}")
        # cv2.imshow("Processed 2", processed_img_2) # Раскомментируйте для просмотра
        # cv2.waitKey(0)
    else:
        print("Тест 2 не удался.")

    # --- Тест 3: Предобработка выключена ---
    print("\n--- Тест 3: Предобработка выключена ---")
    test_config_3 = {'enabled': False}
    processed_img_3 = preprocess_image(test_pil_image, test_config_3)
    if processed_img_3 is not None:
        print(f"Тест 3 завершен. Форма итогового изображения: {processed_img_3.shape}, Тип данных: {processed_img_3.dtype}")
        # cv2.imshow("Processed 3", processed_img_3) # Раскомментируйте для просмотра
        # cv2.waitKey(0)
    else:
        print("Тест 3 не удался.")

    # cv2.destroyAllWindows() # Если использовали imshow
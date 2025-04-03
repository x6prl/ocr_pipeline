import logging
import re

logger = logging.getLogger(__name__)

def clean_text(raw_text: str, config: dict) -> str:
    """
    Очищает сырой текст, полученный от OCR, удаляя лишние пробелы,
    пустые строки и выполняя базовые нормализации для лучшей читаемости.

    Args:
        raw_text (str): Сырой текст после OCR.
        config (dict): Словарь с настройками постобработки (пока не используется).

    Returns:
        str: Очищенный текст.
    """
    if not isinstance(raw_text, str):
        logger.warning("В clean_text передан не строковый тип. Возвращаем как есть.")
        return str(raw_text) # Попытаемся преобразовать в строку для безопасности

    logger.info(f"Начало постобработки текста (исходная длина: {len(raw_text)})...")

    # 1. Удаление Unicode Replacement Character (U+FFFD �)
    cleaned_text = raw_text.replace('\uFFFD', '')

    # 2. Работа со строками:
    lines = cleaned_text.splitlines()
    processed_lines = []
    for line in lines:
        # Убираем пробелы по краям КАЖДОЙ строки
        stripped_line = line.strip()
        # Заменяем множественные пробелы внутри строки одним
        normalized_space_line = ' '.join(stripped_line.split())
        # Добавляем непустые строки в результат
        if normalized_space_line:
            processed_lines.append(normalized_space_line)

    # Соединяем обработанные строки обратно
    cleaned_text = '\n'.join(processed_lines)

    # 3. Нормализация пустых строк между блоками текста (не более одной)
    # Заменяем два или более перевода строки на два (одна пустая строка).
    # Этот шаг важен ПОСЛЕ соединения строк.
    cleaned_text = re.sub(r'\n{2,}', '\n\n', cleaned_text)

    # 4. Финальная очистка пробелов в начале/конце всего текста
    cleaned_text = cleaned_text.strip()

    final_length = len(cleaned_text)
    reduction = len(raw_text) - final_length
    logger.info(f"Постобработка завершена. Итоговая длина: {final_length} (уменьшение на {reduction} символов).")

    return cleaned_text

# --- Тестовый блок остается прежним, можно удалить или обновить для новых кейсов ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
    # ... (тестовые вызовы) ...
    test_text_trailing_space = "Строка с пробелом в конце.   \n   Другая строка.   "
    print("\n--- Исходный текст с пробелами в конце строк ---")
    print(f'"{test_text_trailing_space}"')
    cleaned_trailing = clean_text(test_text_trailing_space, {})
    print("\n--- Очищенный текст ---")
    print(f'"{cleaned_trailing}"')
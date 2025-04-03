import logging
import sys
import os
from logging.handlers import RotatingFileHandler

# --- Расширенный набор цветов ---
class LogColors:
    GREY = "\033[90m"
    LIGHT_BLUE = "\033[94m" # Для времени
    CYAN = "\033[96m"       # Для имени логгера
    GREEN = "\033[92m"      # INFO
    YELLOW = "\033[93m"     # WARNING
    RED = "\033[91m"        # ERROR
    BOLD_RED = "\033[91m\033[1m" # CRITICAL
    RESET = "\033[0m"       # Сброс цвета

# --- Кастомный Formatter ---
class ColoredFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt=None, style='%', use_colors=True):
        super().__init__(fmt, datefmt, style)
        self.use_colors = use_colors
        # Словарь цветов ТОЛЬКО для уровней
        self.level_colors = {
            logging.DEBUG: LogColors.GREY,
            logging.INFO: LogColors.GREEN,
            logging.WARNING: LogColors.YELLOW,
            logging.ERROR: LogColors.RED,
            logging.CRITICAL: LogColors.BOLD_RED,
        }
        # Базовый формат без цветов для фолбека и не-цветного вывода
        self.base_formatter = logging.Formatter(fmt, datefmt, style)

    def format(self, record):
        if not self.use_colors:
            # Если цвета не используются, используем базовый форматтер
            return self.base_formatter.format(record)

        # --- Форматируем с цветами ---
        # Выбираем цвет для уровня
        level_color = self.level_colors.get(record.levelno, LogColors.RESET)

        # Форматируем основные части лога
        log_entry = (
            f"{LogColors.LIGHT_BLUE}{self.formatTime(record, self.datefmt)}{LogColors.RESET} - "
            f"{LogColors.CYAN}{record.name}{LogColors.RESET} - "
            f"[{level_color}{record.levelname}{LogColors.RESET}] - "
            f"{record.getMessage()}" # Сообщение остается стандартного цвета терминала
        )

        # Обработка исключений (traceback) - выводим его цветом уровня
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            # Добавляем traceback с новой строки, окрашенный цветом уровня
            log_entry += f"\n{level_color}{record.exc_text}{LogColors.RESET}"
        if record.stack_info:
            # То же для stack_info, если он есть
            log_entry += f"\n{level_color}{self.formatStack(record.stack_info)}{LogColors.RESET}"

        return log_entry

def setup_logging(config):
    """Настраивает систему логирования на основе конфигурации с кастомными цветами для консоли."""

    log_config = config.get('logging', {})
    log_level_str = log_config.get('level', 'INFO').upper()
    log_file = log_config.get('log_file', None)
    log_to_console = log_config.get('log_to_console', True)

    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(log_level)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    log_format = '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Стандартный форматтер для файла (БЕЗ ЦВЕТОВ)
    standard_formatter = logging.Formatter(log_format, datefmt=date_format)

    # Проверяем поддержку цветов терминалом
    supports_color = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    # Создаем наш кастомный цветной форматтер для консоли
    # Передаем ему базовый формат, он сам разберется с цветами
    colored_formatter = ColoredFormatter(log_format, datefmt=date_format, use_colors=supports_color)

    # Консольный обработчик
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(colored_formatter) # <- Наш новый форматтер
        logger.addHandler(console_handler)

    # Файловый обработчик
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(standard_formatter) # <- Стандартный форматтер для файла
            logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Не удалось настроить файловый логгер для '{log_file}': {e}", exc_info=True)

    logging.info("Система логирования настроена (кастомные цвета).")
    logging.debug(f"Уровень логирования: {log_level_str} ({log_level})")
    if log_to_console:
        logging.debug(f"Логирование в консоль: Включено (Цвета: {'Да' if supports_color else 'Нет'})")
    if log_file:
        logging.debug(f"Логирование в файл: {log_file}")


if __name__ == '__main__':
    # Пример использования для демонстрации цветов:
    test_config = {
        'logging': {
            'level': 'DEBUG', # Поставим DEBUG, чтобы увидеть все уровни
            'log_file': 'test_colored_log_v2.log',
            'log_to_console': True
        }
    }
    setup_logging(test_config)

    logger_main = logging.getLogger('main_app')
    logger_core = logging.getLogger('core.ocr.engine')
    logger_utils = logging.getLogger('utils.helpers')

    logger_main.debug("Сообщение DEBUG: инициализация...")
    logger_utils.info("Сообщение INFO: утилита успешно загружена.")
    logger_core.info("Сообщение INFO: движок OCR готов к работе.")
    logger_main.warning("Сообщение WARNING: найден устаревший параметр в конфиге.")
    logger_core.error("Сообщение ERROR: не удалось распознать фрагмент X.")
    try:
        1 / 0
    except ZeroDivisionError:
        # Логирование исключения (traceback будет окрашен цветом уровня ERROR)
        logger_main.exception("Сообщение CRITICAL с traceback:")

    print("\nПроверьте файл 'test_colored_log_v2.log' - он должен быть без цветовых кодов.")
    print("Проверьте вывод в консоли на наличие разных цветов для времени, имени модуля и уровня.")
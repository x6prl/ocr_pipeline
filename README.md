
**Установка системных зависимостей (Tesseract и Poppler)**

Прежде чем устанавливать Python-библиотеки, нам нужны сами инструменты Tesseract и Poppler (для `pdf2image`). Откройте терминал Ubuntu и выполните:

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-rus poppler-utils python3.13-venv
```

*   `tesseract-ocr`: Основной движок OCR.
*   `tesseract-ocr-rus`: Пакет русского языка для Tesseract (стандартный, не `_best`). Для более высокого качества можно будет позже скачать модели `tessdata_best`.
*   `poppler-utils`: Утилиты для работы с PDF, необходимые для `pdf2image` (включает `pdftoppm`, который используется под капотом).

**Создание виртуального окружения и установка Python-зависимостей**

Очень рекомендуется использовать виртуальное окружение, чтобы изолировать зависимости проекта.

1.  **Перейдите в директорию проекта:**
    ```bash
    cd ocr_pipeline
    ```
2.  **Создайте виртуальное окружение** (папка `venv`):
    ```bash
    python3 -m venv venv
    ```
3.  **Активируйте виртуальное окружение:**
    ```bash
    source venv/bin/activate
    ```
    *Важно:* После активации в начале строки терминала появится `(venv)`. Выполняйте все последующие Python/pip команды в этом активированном окружении. Чтобы деактивировать, просто введите `deactivate`.
4.  **Установите библиотеки из `requirements.txt`:**
    ```bash
    pip install -r requirements.txt
    ```

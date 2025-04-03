# OCR Pipeline for Images and PDFs (Russian Documents)

## Overview

A local OCR pipeline for extracting machine-readable text from images and PDF files. It is optimized for A4-sized, primarily printed Russian-language documents. The system processes files, performs image preprocessing, OCR, postprocessing, and saves structured JSON outputs with traceable metadata.

Designed to run on Ubuntu Linux.

## Features

- Supports input formats: JPG, JPEG, PNG, BMP, TIFF, and PDF.
- **Image preprocessing:**
  - Grayscale conversion.
  - Automatic skew correction (deskew).
  - Adaptive binarization (for photos with uneven lighting).
  - Noise removal (median filter).
  - Fully configurable via `config.yaml`.
- **PDF processing:**
  - Converts PDFs to images per page to save memory.
  - DPI for rendering is configurable.
- **OCR:**
  - Uses Tesseract OCR engine.
  - Russian (and other) language support.
  - Optionally uses high-quality `tessdata_best` models.
- **Postprocessing:**
  - Cleans up extra whitespace and normalizes newlines.
- **Structured output:**
  - JSON output per page/image with text and metadata.
  - Metadata includes original filename, page number, and input path.
- **Configuration:**
  - All options controlled via a single `config.yaml` file.
- **Logging:**
  - Detailed logging to file and optional colored console output.

## System Requirements (Ubuntu)

Before installing Python dependencies, install the following system tools:

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-rus poppler-utils python3.13-venv
```

- `tesseract-ocr`: OCR engine.
- `tesseract-ocr-rus`: Russian language pack for Tesseract.
- `poppler-utils`: Required for PDF to image conversion (`pdf2image` uses `pdftoppm`).
- `python3.13-venv`: For creating Python virtual environments.

## Installation

1. **Clone the repository:**

```bash
git clone https://github.com/x6prl/ocr_pipeline.git
cd ocr_pipeline
```

2. **Create and activate a virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

4. **Configure the project:**

Edit `config.yaml` to set paths and parameters. If you downloaded `tessdata_best` models:

- Create a `tessdata/` folder in the project root.
- Place `.traineddata` files (e.g., `rus.traineddata`) inside it.
- Set `tessdata_dir: "tessdata/"` in the config.

## Usage

1. Place input files (images or PDFs) into the folder specified by `input_dir` (default: `input_data/`).
2. Activate your virtual environment:

```bash
source venv/bin/activate
```

3. Run the main script:

```bash
python main.py
```

4. Output JSON files will be saved in `output_dir` (default: `output_data/`), one per image or PDF page.

## Project Structure

```
ocr_pipeline/
├── main.py                 # Entry point
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── venv/                   # Virtual environment (after setup)
├── input_data/             # Input folder (can contain subfolders)
├── output_data/            # Output folder for JSON results
├── tessdata/               # Optional folder for custom Tesseract models
├── ocr_pipeline.log        # Log file
│
├── core/                   # Processing modules
│   ├── file_handler.py     # File discovery and PDF → image conversion
│   ├── image_processor.py  # Image preprocessing (OpenCV)
│   ├── ocr_engine.py       # OCR engine integration (pytesseract)
│   ├── post_processor.py   # Text cleanup and normalization
│   └── output_handler.py   # JSON output
│
└── utils/
    └── logger.py           # Logging setup
```

## `config.yaml` Overview

```yaml
input_dir: "input_data"
output_dir: "output_data"
tesseract_cmd: null         # Use full path if needed
tessdata_dir: null          # Set to "tessdata/" if using custom models
ocr_language: "rus"
ocr_config: "--psm 3 --oem 1"
pdf_dpi: 300

preprocessing:
  enabled: true
  grayscale: true
  deskew: true
  binarization_method: "adaptive"  # "adaptive", "otsu", or null
  adaptive_thresh_block_size: 15
  adaptive_thresh_C: 10
  noise_removal: "median_3"        # "median_3", "median_5", or null

postprocessing:
  enabled: true

logging:
  level: "INFO"
  log_file: "ocr_pipeline.log"
  log_to_console: true
```

## Output Format (JSON)

Each processed image or PDF page will result in a structured JSON file like:

```json
{
  "document_info": {
    "input_directory": "input_data",
    "relative_path": "subfolder/document.pdf",
    "original_filename": "document.pdf",
    "source_type": "pdf_page",
    "page_number": 2
  },
  "processing_info": {
    "timestamp_utc": "2024-04-03T18:15:30.123Z",
    "duration_sec": 8.45,
    "ocr_engine_lang": "rus",
    "tesseract_config_used": "--psm 3 --oem 1"
  },
  "content": {
    "text": "This is the extracted and cleaned text.\nLine breaks are preserved.\n\nNew paragraphs are separated by an empty line."
  }
}
```

## Troubleshooting

- **`Killed` error (large PDFs):** Caused by out-of-memory. Make sure PDFs are processed page-by-page. Reduce `pdf_dpi` to 200 if needed.
- **`TesseractNotFoundError`:** Ensure `tesseract-ocr` is installed and in your PATH, or set `tesseract_cmd` in config.
- **Low OCR quality:**
  - Tune `preprocessing` options.
  - Use `tessdata_best` models.
  - Try different `--psm` modes (1, 3, 6, 11).
  - Verify correct OCR language in `ocr_language`.
- **Missing language data:** Install with `sudo apt install tesseract-ocr-rus` or provide `.traineddata` in `tessdata/`.

## Roadmap

- Perspective correction and background cropping.
- Support for additional OCR engines (e.g., cloud-based).
- Advanced postprocessing (e.g., hyphenation removal, spellchecking).
- Parallel processing of files/pages for performance.

---

Feel free to contribute, open issues, or fork the project!

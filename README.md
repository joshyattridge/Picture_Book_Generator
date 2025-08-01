# Children's Book PDF Generator

This project is a simple PDF children's book generator. It allows you to provide a list of text paragraphs and images, and generates a PDF where each page contains one paragraph and one image. The generated PDF is formatted for an 8.5×8.5 inch book at **300 dpi**, making it suitable for uploading to Kindle Direct Publishing (KDP).

## Features

- Generate a children's book PDF with one paragraph and one image per page
- Accepts lists of text and images as input
- Outputs a PDF sized for KDP (8.5x8.5 inches)
- Uses [Pillow](https://python-pillow.org/) for image processing
- Uses [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF manipulation (if needed)
- Includes example text and images for testing

## Requirements

- Python 3.7+
- [Pillow](https://python-pillow.org/)
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- [OpenAI](https://github.com/openai/openai-python)
- [httpx](https://github.com/encode/httpx)

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

1. Prepare a list of text paragraphs (one for each page).
2. Prepare a list of image file paths (one for each page).
3. Run the script to generate the PDF.

Example usage:

```python
from book_generator import generate_book

texts = [
    "Once upon a time, there was a little fox who loved to explore the forest.",
    "One sunny day, the fox found a sparkling river and made new friends.",
    "At night, the stars twinkled above as the fox dreamed of new adventures."
]

images = [
    "images/fox.png",
    "images/river.png",
    "images/stars.png"
]

generate_book(texts, images, output_pdf="childrens_book.pdf")
```

### Command line usage

The repository also includes a command line script that can process one or more
book folders contained in the `books/` directory:

```bash
python generate_book.py                  # generate PDFs for all books
python generate_book.py --book Peters_Pickle        # only process one book
python generate_book.py --book BookA --book BookB   # multiple books
python generate_book.py --book Peters_Pickle --skip-cover    # no cover PDF
python generate_book.py --book Peters_Pickle -o build        # custom output dir
```

## Example Content

- Example text and images are included in the repository for testing.
- The script will generate a PDF named `childrens_book.pdf` with three pages, each containing a paragraph and an image.

## KDP Compatibility

- The generated PDFs use 300 dpi pages measuring 8.5×8.5 inches.
- Interior pages can include bleed when the ``USE_BLEED`` constant in
  ``generate_book.py`` is set to ``True``. This expands the page size to
  8.625×8.75 inches as recommended by KDP.
- Cover images are automatically expanded to include bleed. The back panel is on the left and the front panel on the right of the PDF spread.
- Spine text is added when the book has 100 pages or more, but the script does **not** overlay the title on the front cover image.
- Font sizes are scaled for 300 dpi pages so text remains clear when printed.
- Please review KDP's latest guidelines for any additional requirements before uploading.

## License

MIT License

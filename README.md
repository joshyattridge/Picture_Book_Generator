# Children's Picture Book Generator

Generate a fully illustrated children's book with text and images, then build print‑ready PDFs sized for 8.5×8.5 inches at 300 dpi (KDP‑friendly).

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`
  - Pillow
  - pdfplumber
  - openai
  - httpx

## What It Does

- Creates a book folder under `books/<Title_Slug>/` containing:
  - `book_text.txt` — final accepted story text
  - `images/cover.jpg`, `images/back.jpg`, `images/page1.jpg..pageN.jpg`
  - `cover.pdf` and `manuscript.pdf` (final PDFs)
- Always regenerates story text and all images each run.
- Asks once if you accept the generated story; if not, exits immediately.
- Fails fast if any image generation fails (no placeholder images).
- Supports a demo mode with offline, local placeholder outputs.

## CLI Usage

The generator is fully CLI‑driven — no saved prompts or reuse.

- Demo mode (no API key required):

  ```bash
  python generate_book.py \
    --demo \
    --title "Space Cats" \
    --topic "Cats exploring outer space" \
    --pages 12 \
    --book-type story \
    --style "cute watercolor" \
    --cover-reference path/to/reference.jpg  # optional
  ```

- Real mode (API key required):

  ```bash
  python generate_book.py \
    --api-key sk-... \
    --title "Forest Friends" \
    --topic "Woodland animal adventures" \
    --pages 12 \
    --book-type rhyme \
    --style "bright, cartoon style"
  ```

### Arguments

- `--title`: Book title (used to name the output directory)
- `--topic`: Short description of what the book is about
- `--pages`: Number of story pages (minimum 12)
- `--book-type`: Style of writing, e.g. `story` or `rhyme`
- `--style`: Illustration style (free text)
- `--cover-reference`: Optional path to an image used to guide visual consistency
- `--demo` / `-demo`: Run offline with local demo text and images
- `--api-key`: OpenAI API key (required unless `--demo` is used)

Notes:
- The script prints the full generated story and asks for acceptance:
  - Enter yes/y (or press Enter) to continue and save it
  - Any other answer exits without saving or generating images
- Each run regenerates everything; there is no reuse mode.

## Building PDFs Only

You can rebuild PDFs for existing book folders with `build_book.py`:

```bash
python build_book.py                  # generate PDFs for all books
python build_book.py --book Peters_Pickle        # only process one book
python build_book.py --book BookA --book BookB   # multiple books
python build_book.py --book Peters_Pickle --skip-cover    # no cover PDF
python build_book.py --book Peters_Pickle -o build        # custom output dir
```

## Output Format and KDP

- PDFs are 8.5×8.5 inches at 300 dpi, suitable for KDP.
- Cover and back cover JPGs are generated and then compiled into PDFs.
- Review KDP’s latest specs before uploading.

## License

MIT License

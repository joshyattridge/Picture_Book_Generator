"""
generate_book.py
==================

This script generates a simple children's picture book as a PDF.  It takes
paragraphs of text from a text file and a corresponding set of images and
produces a PDF sized for an 8.5×8.5‑inch book at 300 dpi (2550 px square).

The layout comprises a cover page, followed by a pair of pages for each
paragraph: the first page presents the illustration and the second page
presents the text on a white background.  The font size and line wrapping
have been tuned so that text sits comfortably on the page without
overflowing.

To change the content, update ``books/MyBook/book_text.txt`` and the images
stored in ``books/MyBook/images``.  The output PDF will be written to
``books/MyBook/MyBook_output.pdf``.
"""

import os
from PIL import Image, ImageDraw, ImageFont

# Constants for an 8.5×8.5‑inch square book at 300 dpi
INCH = 300
PAGE_SIZE = (8.5 * INCH, 8.5 * INCH)  # (width, height) in pixels
# Margin around text content (in pixels)
MARGIN = 100
# Base font size for body text.  This can be tweaked to fit more or less
# content on a page.  At 100 px the average line height is around 100 px on a
# 2550 px page, leaving room for several lines of text.
FONT_SIZE = 100

# Book configuration
BOOKS_DIR = 'books'
BOOK_NAME = 'MyBook'
BOOK_PATH = os.path.join(BOOKS_DIR, BOOK_NAME)
IMAGES_PATH = os.path.join(BOOK_PATH, 'images')
TEXT_PATH = os.path.join(BOOK_PATH, 'book_text.txt')
OUTPUT_PDF = os.path.join(BOOK_PATH, f'{BOOK_NAME}_output.pdf')


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Try to load a scalable TrueType font; fall back to the default font.

    Attempts to load fonts in the following order:
    1. DejaVuSans-Bold (Linux)
    2. Arial (Windows/macOS)
    3. Helvetica (macOS)
    4. System font paths for macOS
    5. Default PIL font (not scalable)

    Args:
        size: Font size in pixels.

    Returns:
        A PIL ``ImageFont`` instance.
    """
    font_paths = [
        "DejaVuSans-Bold.ttf",  # Linux
        "Arial.ttf",            # Windows/macOS
        "Helvetica.ttf",        # macOS
        "/Library/Fonts/Arial.ttf",  # macOS system path
        "/Library/Fonts/Helvetica.ttf",  # macOS system path
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS system path
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",  # macOS system path
    ]
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    # Fallback to the default font (may not be scalable)
    return ImageFont.load_default()


FONT = get_font(FONT_SIZE)


def wrap_text(text: str, draw: ImageDraw.Draw, font: ImageFont.ImageFont, max_width: float) -> list[str]:
    """Split text into a list of lines that fit within a given width, preserving explicit newlines."""
    # Split the text into lines using explicit newlines
    raw_lines = text.split('\n')
    wrapped_lines: list[str] = []
    for raw_line in raw_lines:
        if not raw_line.strip():
            # Preserve empty lines
            wrapped_lines.append("")
            continue
        words = raw_line.split()
        current = ''
        for word in words:
            test = f'{current} {word}'.strip()
            w, _ = draw.textsize(test, font=font)
            if w > max_width and current:
                wrapped_lines.append(current)
                current = word
            else:
                current = test
        if current:
            wrapped_lines.append(current)
    return wrapped_lines


def create_text_page(paragraph: str) -> Image.Image:
    """Create a white page with centred, wrapped text for a given paragraph, preserving explicit newlines and auto-scaling font size to fit."""
    min_font_size = 24
    font_size = FONT_SIZE
    max_width = PAGE_SIZE[0] - 2 * MARGIN
    img = Image.new('RGB', (int(PAGE_SIZE[0]), int(PAGE_SIZE[1])), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    while font_size >= min_font_size:
        font = get_font(font_size)
        lines = wrap_text(paragraph, draw, font, max_width)
        line_height = font.getsize('Ag')[1]
        spacing = 10
        total_height = line_height * len(lines) + spacing * (len(lines) - 1)
        if total_height <= PAGE_SIZE[1] - 2 * MARGIN:
            break
        font_size -= 2  # Decrease font size and try again
    else:
        # If we exit the loop without breaking, use the minimum font size
        font = get_font(min_font_size)
        lines = wrap_text(paragraph, draw, font, max_width)
        line_height = font.getsize('Ag')[1]
        spacing = 10
        total_height = line_height * len(lines) + spacing * (len(lines) - 1)

    y = (PAGE_SIZE[1] - total_height) // 2
    for line in lines:
        if line == "":
            y += line_height + spacing
            continue
        w, _ = draw.textsize(line, font=font)
        x = (PAGE_SIZE[0] - w) // 2
        draw.text((x, y), line, font=font, fill=(0, 0, 0))
        y += line_height + spacing
    return img


def centre_crop_image(img: Image.Image) -> Image.Image:
    """Resize and crop an image to fill the square page while preserving aspect ratio.

    The image is resized so that at least one dimension matches the page size,
    then the surplus in the other dimension is centre-cropped away.

    Args:
        img: A PIL ``Image`` instance.

    Returns:
        A new ``Image`` object of size ``PAGE_SIZE``.
    """
    img_ratio = img.width / img.height
    page_ratio = PAGE_SIZE[0] / PAGE_SIZE[1]
    if img_ratio > page_ratio:
        # Image is wider than page: scale height to match, crop width
        new_height = int(PAGE_SIZE[1])
        new_width = int(new_height * img_ratio)
        resized = img.resize((new_width, new_height), Image.LANCZOS)
        left = (new_width - PAGE_SIZE[0]) // 2
        crop = resized.crop((left, 0, left + int(PAGE_SIZE[0]), int(PAGE_SIZE[1])))
    else:
        # Image is taller than page: scale width to match, crop height
        new_width = int(PAGE_SIZE[0])
        new_height = int(new_width / img_ratio)
        resized = img.resize((new_width, new_height), Image.LANCZOS)
        top = (new_height - PAGE_SIZE[1]) // 2
        crop = resized.crop((0, top, int(PAGE_SIZE[0]), top + int(PAGE_SIZE[1])))
    return crop


def generate_book(book_name: str) -> None:
    """Generate the picture book PDF for a given book folder."""
    book_path = os.path.join(BOOKS_DIR, book_name)
    images_path = os.path.join(book_path, 'images')
    text_path = os.path.join(book_path, 'book_text.txt')
    output_pdf = os.path.join(book_path, f'{book_name}_output.pdf')
    # Read paragraphs from the text file
    if not os.path.exists(text_path):
        print(f"[SKIP] No book_text.txt found for {book_name}")
        return
    with open(text_path, 'r', encoding='utf-8') as f:
        content = f.read()
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    # Prepare list of image paths: cover plus one per paragraph
    image_files: list[str] = [os.path.join(images_path, 'cover.jpg')]
    for i in range(1, len(paragraphs) + 1):
        image_files.append(os.path.join(images_path, f'page{i}.jpg'))
    pages: list[Image.Image] = []
    # Create cover page
    if not os.path.exists(image_files[0]):
        print(f"[SKIP] No cover.jpg found for {book_name}")
        return
    cover_img = Image.open(image_files[0]).convert('RGB')
    cover_page = centre_crop_image(cover_img)
    pages.append(cover_page)
    # Create pages for each paragraph
    for idx, paragraph in enumerate(paragraphs):
        img_path = image_files[idx + 1]
        if not os.path.exists(img_path):
            print(f"[SKIP] No image for page {idx+1} in {book_name}")
            return
        img = Image.open(img_path).convert('RGB')
        pages.append(centre_crop_image(img))
        pages.append(create_text_page(paragraph))
    # Add back cover page if it exists
    back_cover_path = os.path.join(images_path, 'back.jpg')
    if os.path.exists(back_cover_path):
        back_img = Image.open(back_cover_path).convert('RGB')
        back_page = centre_crop_image(back_img)
        pages.append(back_page)
    # Ensure output directory exists
    os.makedirs(book_path, exist_ok=True)
    # Save the pages as a single PDF
    pages[0].save(output_pdf, save_all=True, append_images=pages[1:])
    print(f'PDF generated at {output_pdf}')


def main():
    # Loop through all subdirectories in books/
    for book_name in os.listdir(BOOKS_DIR):
        book_path = os.path.join(BOOKS_DIR, book_name)
        if os.path.isdir(book_path):
            print(f'Generating book for: {book_name}')
            generate_book(book_name)


if __name__ == '__main__':
    main()
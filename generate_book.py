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

    DejaVuSans-Bold is commonly available on Linux systems.  If it cannot be
    found, the default bitmap font is returned.

    Args:
        size: Font size in pixels.

    Returns:
        A PIL ``ImageFont`` instance.
    """
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            # Try a second common font
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            # Fallback to the default font (may not be scalable)
            return ImageFont.load_default()


FONT = get_font(FONT_SIZE)


def wrap_text(text: str, draw: ImageDraw.Draw, font: ImageFont.ImageFont, max_width: float) -> list[str]:
    """Split text into a list of lines that fit within a given width.

    Args:
        text: The raw paragraph to wrap.
        draw: An ``ImageDraw`` instance used to measure text.
        font: The font used for measurement.
        max_width: Maximum width for each line in pixels.

    Returns:
        A list of strings, each representing a line of wrapped text.
    """
    words = text.split()
    lines: list[str] = []
    current = ''
    for word in words:
        test = f'{current} {word}'.strip()
        w, _ = draw.textsize(test, font=font)
        if w > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def create_text_page(paragraph: str) -> Image.Image:
    """Create a white page with centred, wrapped text for a given paragraph.

    Args:
        paragraph: The paragraph to render.

    Returns:
        A PIL ``Image`` representing the page.
    """
    img = Image.new('RGB', (int(PAGE_SIZE[0]), int(PAGE_SIZE[1])), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    max_width = PAGE_SIZE[0] - 2 * MARGIN
    lines = wrap_text(paragraph, draw, FONT, max_width)
    # Compute total height of the block of text (line height plus spacing)
    line_height = FONT.getsize('Ag')[1]
    spacing = 20  # space between lines
    total_height = line_height * len(lines) + spacing * (len(lines) - 1)
    # Start drawing so the block is vertically centred
    y = (PAGE_SIZE[1] - total_height) // 2
    for line in lines:
        w, _ = draw.textsize(line, font=FONT)
        x = (PAGE_SIZE[0] - w) // 2
        draw.text((x, y), line, font=FONT, fill=(0, 0, 0))
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


def generate_book() -> None:
    """Generate the picture book PDF from the configured book folder."""
    # Read paragraphs from the text file
    with open(TEXT_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    # Prepare list of image paths: cover plus one per paragraph
    image_files: list[str] = [os.path.join(IMAGES_PATH, 'cover.jpg')]
    for i in range(1, len(paragraphs) + 1):
        image_files.append(os.path.join(IMAGES_PATH, f'page{i}.jpg'))
    pages: list[Image.Image] = []
    # Create cover page
    cover_img = Image.open(image_files[0]).convert('RGB')
    cover_page = centre_crop_image(cover_img)
    pages.append(cover_page)
    # Create pages for each paragraph
    for idx, paragraph in enumerate(paragraphs):
        # Illustration page
        img = Image.open(image_files[idx + 1]).convert('RGB')
        pages.append(centre_crop_image(img))
        # Text page
        pages.append(create_text_page(paragraph))
    # Ensure output directory exists
    os.makedirs(BOOK_PATH, exist_ok=True)
    # Save the pages as a single PDF
    pages[0].save(OUTPUT_PDF, save_all=True, append_images=pages[1:])
    print(f'PDF generated at {OUTPUT_PDF}')


if __name__ == '__main__':
    generate_book()
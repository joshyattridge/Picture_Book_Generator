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
import math

# Constants for an 8.5×8.5‑inch square book at 300 dpi
INCH = 300
# Define the finished page dimensions in pixels for an 8.5×8.5 inch book
PAGE_SIZE = (8.5 * INCH, 8.5 * INCH)

# Margin around text content (in pixels).  This is used to inset the text
# panel from the edge of the page to avoid cramped layouts.  It will also
# control space for decorative borders and page numbers.
MARGIN = 150

# Base font size for body text.  This value will be scaled down if the
# paragraph is too long to comfortably fit within the available area.  A
# slightly smaller default makes it easier to accommodate longer sentences
# while still maintaining a child‑friendly appearance.
FONT_SIZE = 80

# Colours used throughout the book.  Pastel shades are deliberately chosen
# because they are soft and appealing to children.  New pages cycle through
# these colours to add variety without clashing.
BACKGROUND_COLOURS = [
    (255, 239, 213),  # papaya whip
    (255, 228, 225),  # misty rose
    (240, 255, 240),  # honeydew
    (224, 255, 255),  # light cyan
    (255, 240, 245),  # lavender blush
]

TEXT_COLOUR = (40, 40, 40)  # dark grey for comfortable reading
PANEL_FILL = (255, 255, 255)  # white panel behind text for contrast
PANEL_BORDER = (200, 200, 200)  # light grey border around text panel
PAGE_NUMBER_COLOUR = (120, 120, 120)


def _brightness(colour: tuple[int, int, int]) -> float:
    """Compute a luminance value from an RGB colour.

    The returned value is a weighted sum approximating human perception of
    brightness.  It falls in the range 0–255.
    """
    r, g, b = colour
    return 0.299 * r + 0.587 * g + 0.114 * b


def add_page_number(img: Image.Image, page_index: int) -> Image.Image:
    """Draw a small page number at the bottom centre of an image.

    This helper is used for image pages and back covers so that the page
    numbers are consistent throughout the book.  The colour of the page
    number is chosen dynamically based on the luminance of the bottom strip
    of the image to ensure adequate contrast.

    Args:
        img: The image onto which to draw the page number.  The image is
            copied before modification.
        page_index: Zero‑based index of the page.

    Returns:
        A new ``Image`` object with the page number drawn.
    """
    result = img.copy().convert('RGBA')
    # Determine whether the bottom of the image is light or dark.  Sample a
    # horizontal strip across the bottom 10% of the page to compute average
    # brightness.
    w, h = result.size
    strip_height = max(1, int(h * 0.1))
    strip = result.crop((0, h - strip_height, w, h)).convert('RGB')
    pixels = list(strip.getdata())
    avg_brightness = sum(_brightness(p) for p in pixels) / len(pixels)
    # Choose text colour based on luminance: dark text on light backgrounds
    # and vice versa.
    if avg_brightness > 180:
        colour = (60, 60, 60, 255)
    else:
        colour = (230, 230, 230, 255)
    # Use the page index itself as the displayed number so that the first
    # interior page (index 1) is numbered 1.  The cover page (index 0)
    # is not passed into this function, so numbering naturally starts from 1.
    number = str(page_index)
    draw = ImageDraw.Draw(result)
    font = get_font(int(FONT_SIZE * 0.4))
    bbox = draw.textbbox((0, 0), number, font=font)
    num_w = bbox[2] - bbox[0]
    num_h = bbox[3] - bbox[1]
    x = (w - num_w) // 2
    y = int(h - MARGIN * 0.8 - num_h)
    # Optionally draw a subtle shadow for improved contrast
    shadow_offset = 1
    shadow_colour = (0, 0, 0, 100) if avg_brightness > 180 else (255, 255, 255, 100)
    draw.text((x + shadow_offset, y + shadow_offset), number, font=font, fill=shadow_colour)
    draw.text((x, y), number, font=font, fill=colour)
    return result.convert('RGB')


def _draw_star(draw: ImageDraw.ImageDraw, centre: tuple[float, float], size: float, fill: tuple[int, int, int]):
    """Draw a five‑pointed star centred at the given coordinates.

    Args:
        draw: The drawing context.
        centre: (x, y) coordinates of the star's centre.
        size: The outer radius of the star.
        fill: RGB colour tuple for the star.
    """
    cx, cy = centre
    points: list[tuple[float, float]] = []
    for i in range(5):
        outer_angle = math.radians(90 + i * 72)
        inner_angle = math.radians(90 + i * 72 + 36)
        outer = (cx + size * math.cos(outer_angle), cy - size * math.sin(outer_angle))
        inner = (cx + size * 0.5 * math.cos(inner_angle), cy - size * 0.5 * math.sin(inner_angle))
        points.append(outer)
        points.append(inner)
    draw.polygon(points, fill=fill)

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

# Try to load a playful font for headings and cover pages.  If unavailable
# fallback to the normal body font.  Additional fonts may be added here in
# priority order to customise the look and feel; the first existing font is
# chosen.
def get_heading_font(size: int) -> ImageFont.ImageFont:
    heading_candidates = [
        # Common playful fonts that may be installed on a host system
        "ComicSansMS.ttf",
        "Comic Sans MS.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    for font_path in heading_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return get_font(size)


def wrap_text(text: str, draw: ImageDraw.Draw, font: ImageFont.ImageFont, max_width: float) -> list[str]:
    """Split text into lines that fit within a specified width.

    The function respects explicit newline characters in the input text.
    Each line is assembled word by word and measured using PIL's
    ``textbbox`` for accurate sizing.  When the line exceeds ``max_width`` it
    is committed and a new line is started.

    Args:
        text: The raw text to wrap.
        draw: A ``ImageDraw`` instance used for measurement.
        font: The font in which the text will be rendered.
        max_width: The maximum allowed width in pixels for a single line.

    Returns:
        A list of strings representing the wrapped lines.
    """
    raw_lines = text.split('\n')
    wrapped_lines: list[str] = []
    for raw_line in raw_lines:
        if not raw_line.strip():
            wrapped_lines.append("")
            continue
        words = raw_line.split()
        current = ''
        for word in words:
            test = f'{current} {word}'.strip()
            # Use textbbox to measure width
            bbox = draw.textbbox((0, 0), test, font=font)
            width = bbox[2] - bbox[0]
            if width > max_width and current:
                wrapped_lines.append(current)
                current = word
            else:
                current = test
        if current:
            wrapped_lines.append(current)
    return wrapped_lines


def create_text_page(paragraph: str, page_index: int) -> Image.Image:
    """Create a decorated page for a given paragraph.

    The resulting page has a pastel background, a rounded white panel
    containing the paragraph, and a page number centred at the bottom.  Text
    wrapping respects explicit newlines and scales down automatically if the
    content would otherwise overflow the panel.  Colours are selected from
    ``BACKGROUND_COLOURS`` based on the page index to provide variety across
    multiple pages without having to tailor for any specific book.

    Args:
        paragraph: The paragraph of text to render.
        page_index: Zero‑based index of the page within the book (cover page
            included).  This is used to select background colours and to
            determine the page number printed at the bottom.

    Returns:
        An ``Image`` object representing the fully laid out page.
    """
    # Pick a pastel background colour using round‑robin selection
    bg_colour = BACKGROUND_COLOURS[page_index % len(BACKGROUND_COLOURS)]
    img = Image.new('RGB', (int(PAGE_SIZE[0]), int(PAGE_SIZE[1])), bg_colour)
    draw = ImageDraw.Draw(img)
    # Define an inner panel for the text with rounded corners.  This panel
    # separates the content from the background and improves readability.
    panel_rect = (
        MARGIN,
        MARGIN,
        PAGE_SIZE[0] - MARGIN,
        PAGE_SIZE[1] - MARGIN * 1.5,  # leave extra space at bottom for page numbers
    )
    # Draw the panel.  We intentionally omit the border so the panel blends
    # softly with the pastel background.  Use rounded_rectangle if
    # available; fall back to a normal rectangle on older PIL versions.
    try:
        draw.rounded_rectangle(panel_rect, radius=40, fill=PANEL_FILL, outline=None)
    except Exception:
        draw.rectangle(panel_rect, fill=PANEL_FILL, outline=None)

    # Add decorative stars at the top corners.  Stars are drawn in a colour
    # slightly darker than the background to stand out without overwhelming
    # the page.  They are positioned relative to the page margins.
    star_colour = tuple(max(0, int(c * 0.8)) for c in bg_colour)
    star_size = 30
    _draw_star(draw, (MARGIN / 2, MARGIN / 2), star_size, star_colour)
    _draw_star(draw, (PAGE_SIZE[0] - MARGIN / 2, MARGIN / 2), star_size, star_colour)

    # Determine the maximum width for text inside the panel
    max_width = panel_rect[2] - panel_rect[0] - 2 * 40  # internal padding
    # Start with the base font size and reduce as necessary
    min_font_size = 20
    font_size = FONT_SIZE
    # Temporary drawing context used for measuring text.  We'll reuse 'draw'.
    # Use a playful heading font throughout the text to make it feel more
    # child‑friendly.  If the desired font is unavailable the helper
    # gracefully falls back to a standard font.
    while font_size >= min_font_size:
        font = get_heading_font(font_size)
        lines = wrap_text(paragraph, draw, font, max_width)
        # Compute line height via textbbox for accurate metrics
        bbox = font.getbbox('Ag')
        line_height = bbox[3] - bbox[1]
        spacing = int(font_size * 0.25)
        total_height = line_height * len(lines) + spacing * (len(lines) - 1)
        if total_height <= (panel_rect[3] - panel_rect[1]) - 2 * 40:
            break
        font_size -= 2
    else:
        font = get_heading_font(min_font_size)
        lines = wrap_text(paragraph, draw, font, max_width)
        bbox = font.getbbox('Ag')
        line_height = bbox[3] - bbox[1]
        spacing = int(min_font_size * 0.25)
        total_height = line_height * len(lines) + spacing * (len(lines) - 1)
    # Compute initial y coordinate to vertically centre content within the panel
    y = panel_rect[1] + ((panel_rect[3] - panel_rect[1]) - total_height) // 2
    # Draw each line onto the panel.  To make the text pop, draw a subtle
    # shadow behind each line before the primary text.  The shadow colour is
    # a mid‑grey that contrasts gently against the white panel without
    # overpowering the main text.  Lines containing only whitespace are
    # handled separately to preserve vertical spacing.
    for line in lines:
        if line == "":
            y += line_height + spacing
            continue
        # Use textbbox to compute width accurately
        text_bbox = draw.textbbox((0, 0), line, font=font)
        w = text_bbox[2] - text_bbox[0]
        # Centre the text within the panel with a 40px horizontal padding
        x = panel_rect[0] + (max_width - w) // 2 + 40
        # Draw shadow slightly offset
        shadow_offset = 2
        shadow_colour = (180, 180, 180)
        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=shadow_colour)
        # Draw the primary text
        draw.text((x, y), line, font=font, fill=TEXT_COLOUR)
        y += line_height + spacing
    # Add page number at the bottom centre.  Page numbers start at 1 for
    # the first interior page (page_index 1), so we simply use page_index
    # itself here.  The cover page is not processed by this function.
    page_number = page_index
    num_text = str(page_number)
    pn_font = get_font(int(FONT_SIZE * 0.4))
    num_bbox = draw.textbbox((0, 0), num_text, font=pn_font)
    num_w = num_bbox[2] - num_bbox[0]
    num_h = num_bbox[3] - num_bbox[1]
    num_x = (PAGE_SIZE[0] - num_w) // 2
    num_y = int(PAGE_SIZE[1] - MARGIN * 0.8 - num_h)
    draw.text((num_x, num_y), num_text, font=pn_font, fill=PAGE_NUMBER_COLOUR)
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
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        left = (new_width - PAGE_SIZE[0]) // 2
        crop = resized.crop((left, 0, left + int(PAGE_SIZE[0]), int(PAGE_SIZE[1])))
    else:
        # Image is taller than page: scale width to match, crop height
        new_width = int(PAGE_SIZE[0])
        new_height = int(new_width / img_ratio)
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        top = (new_height - PAGE_SIZE[1]) // 2
        crop = resized.crop((0, top, int(PAGE_SIZE[0]), top + int(PAGE_SIZE[1])))
    return crop


def get_title_from_name(book_name: str) -> str:
    """Convert a book folder name into a nicely spaced title.

    E.g. ``"Peters_Pickle"`` becomes ``"Peters Pickle"`` and
    ``"MyFantasticBook"`` becomes ``"My Fantastic Book"``.

    Args:
        book_name: Raw name of the book directory.

    Returns:
        A human‑friendly title string.
    """
    # Replace underscores with spaces
    title = book_name.replace('_', ' ')
    # If the name is CamelCase, insert spaces before capitals (excluding the
    # first character)
    spaced = []
    for i, ch in enumerate(title):
        if i > 0 and ch.isupper() and title[i - 1].islower():
            spaced.append(' ')
        spaced.append(ch)
    return ''.join(spaced)


def create_cover_page(cover_img: Image.Image, book_name: str) -> Image.Image:
    """Create an enhanced cover page.

    This function centre‑crops the provided image to square dimensions and
    overlays a semi‑transparent panel near the bottom containing the book
    title.  The title is derived from the directory name and uses a larger
    heading font.  If the underlying image is dark, the light panel ensures
    the text remains legible.

    Args:
        cover_img: Source PIL image for the cover.
        book_name: Name of the book directory.

    Returns:
        A PIL ``Image`` representing the decorated cover page.
    """
    # Simply centre‑crop the cover image.  We intentionally avoid overlaying
    # text here because many cover images will contain their own titles or
    # artwork.  By refraining from adding additional elements we maintain
    # flexibility across a variety of books.  Page numbers are handled
    # separately by the calling code and are not drawn on the cover.
    return centre_crop_image(cover_img)


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
    cover_page = create_cover_page(cover_img, book_name)
    pages.append(cover_page)
    # Create pages for each paragraph
    for idx, paragraph in enumerate(paragraphs):
        img_path = image_files[idx + 1]
        if not os.path.exists(img_path):
            print(f"[SKIP] No image for page {idx+1} in {book_name}")
            return
        img = Image.open(img_path).convert('RGB')
        # Determine the page index for the illustration page
        page_idx = len(pages)
        # Centre crop the illustration and add a page number (skipping the cover)
        illustration = add_page_number(centre_crop_image(img), page_idx)
        pages.append(illustration)
        # Now create the corresponding text page.  Its index will be the
        # current length of pages (image was just appended).
        page_idx = len(pages)
        pages.append(create_text_page(paragraph, page_idx))
    # Add back cover page if it exists.  The back cover receives the same
    # cropping treatment as the interior images but does not overlay a panel.
    back_cover_path = os.path.join(images_path, 'back.jpg')
    if os.path.exists(back_cover_path):
        back_img = Image.open(back_cover_path).convert('RGB')
        # Determine the page index for the back cover
        page_idx = len(pages)
        back_page = add_page_number(centre_crop_image(back_img), page_idx)
        pages.append(back_page)
    # Ensure output directory exists
    os.makedirs(book_path, exist_ok=True)
    # Save the pages as a single PDF
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
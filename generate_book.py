"""Generate a simple 8.5×8.5 inch picture book PDF."""

import os
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Constants for an 8.5×8.5 inch square book at 300 dpi
# Use 300 pixels per inch so that the output PDF meets KDP’s resolution
# requirements.
INCH = 300

# ``USE_BLEED`` controls whether the interior pages include bleed. When set to
# ``True`` the page dimensions follow KDP's formula of trim width + 0.125″ and
# trim height + 0.25″. Keep this ``False`` if you disable bleed during upload.
USE_BLEED = True

TRIM_WIDTH_IN = 8.5
TRIM_HEIGHT_IN = 8.5
PAGE_WIDTH_IN = TRIM_WIDTH_IN + (0.125 if USE_BLEED else 0)
PAGE_HEIGHT_IN = TRIM_HEIGHT_IN + (0.25 if USE_BLEED else 0)

# Define the finished page dimensions in pixels.
PAGE_SIZE = (PAGE_WIDTH_IN * INCH, PAGE_HEIGHT_IN * INCH)

# Margin around text content (in pixels). KDP requires at least 0.25″ without
# bleed or 0.375″ with bleed. Match the appropriate value so nothing is
# trimmed during printing.
MARGIN = int((0.375 if USE_BLEED else 0.25) * INCH)

# Base font size for body text.  This value will be scaled down if the
# paragraph is too long to comfortably fit within the available area.  A
# slightly smaller default makes it easier to accommodate longer sentences
# while still maintaining a child‑friendly appearance.
# Scale font sizes relative to the DPI so text remains legible when
# increasing resolution. The original script used a 75 dpi canvas with
# a minimum font size of 20 px. At 300 dpi that equates to roughly
# 80 px. ``FONT_SIZE`` starts slightly smaller so long passages can be
# scaled down if needed, while ``MIN_FONT_SIZE`` represents the target
# size for normal pages.
FONT_SIZE = int(INCH * 0.1333)  # ~40px at 300 dpi
MIN_FONT_SIZE = int(INCH * 0.2667)  # ~80px at 300 dpi

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

# Book configuration
BOOKS_DIR = 'books'


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

    The resulting page has a pastel background and a rounded white panel
    containing the paragraph. Text wrapping respects explicit newlines and 
    scales down automatically if the content would otherwise overflow the panel.  
    Colours are selected from ``BACKGROUND_COLOURS`` based on the page index 
    to provide variety across multiple pages without having to tailor for any 
    specific book. Page numbers are not included for a cleaner children's book design.

    Args:
        paragraph: The paragraph of text to render.
        page_index: Zero‑based index of the page within the book (cover page
            included).  This is used to select background colours.

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
        PAGE_SIZE[1] - MARGIN,  # no extra space needed since page numbers are removed
    )
    # Draw the panel.  We intentionally omit the border so the panel blends
    # softly with the pastel background.  Use rounded_rectangle if
    # available; fall back to a normal rectangle on older PIL versions.
    try:
        draw.rounded_rectangle(panel_rect, radius=40, fill=PANEL_FILL, outline=None)
    except Exception:
        draw.rectangle(panel_rect, fill=PANEL_FILL, outline=None)


    # Determine the maximum width for text inside the panel
    max_width = panel_rect[2] - panel_rect[0] - 2 * 40  # internal padding
    # Start with the preferred font size and reduce as necessary. ``MIN_FONT_SIZE``
    # represents the smallest acceptable text size on the high‑resolution
    # pages.
    min_font_size = MIN_FONT_SIZE
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
        # Only draw the primary text (no shadow)
        draw.text((x, y), line, font=font, fill=TEXT_COLOUR)
        y += line_height + spacing
    # Page numbers removed for children's books - cleaner design for KDP
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
    # ``ImageOps.fit`` handles the scaling and cropping in one step using
    # floating‑point math internally, which avoids tiny rounding errors that can
    # leave stray borders.  The resulting image is guaranteed to match
    # ``PAGE_SIZE`` exactly.
    size = (int(round(PAGE_SIZE[0])), int(round(PAGE_SIZE[1])))
    return ImageOps.fit(img, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))


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


def create_cover_page(cover_img: Image.Image, title: str) -> Image.Image:
    """Prepare the front cover image without adding any text.

    The image is centre‑cropped to the page size so that it fills the
    bleed area on all sides.  No additional title overlay is applied
    because many cover designs already include the book title within
    the artwork.

    Args:
        cover_img: Source PIL image for the cover.
        title: Full book title to render on the front cover.

    Returns:
        A PIL ``Image`` representing the decorated cover page.
    """
    # Simply centre‑crop the provided image and return it. The caller is
    # responsible for adding any spine text when needed.
    return centre_crop_image(cover_img)


# KDP-required cover size for 8.5 x 8.5 in book (with bleed):
COVER_WIDTH_INCHES = 17.306
COVER_HEIGHT_INCHES = 8.750
DPI = 300
COVER_SIZE = (
    int(round(COVER_WIDTH_INCHES * DPI)),
    int(round(COVER_HEIGHT_INCHES * DPI)),
)


def generate_book(book_name: str, *, output_dir: str | None = None, skip_cover: bool = False) -> None:
    """Generate the picture book PDF for a given book folder."""
    book_path = os.path.join(BOOKS_DIR, book_name)
    images_path = os.path.join(book_path, 'images')
    text_path = os.path.join(book_path, 'book_text.txt')
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_pdf = os.path.join(output_dir, f'{book_name}_output.pdf')
        cover_pdf = os.path.join(output_dir, f'{book_name}_cover.pdf')
    else:
        output_pdf = os.path.join(book_path, f'{book_name}_output.pdf')
        cover_pdf = os.path.join(book_path, f'{book_name}_cover.pdf')
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
    # --- COVER & BACK COVER HANDLING ---
    # Load cover and back cover images if they exist
    title = get_title_from_name(book_name)
    if not skip_cover:
        if os.path.exists(image_files[0]):
            cover_page = create_cover_page(Image.open(image_files[0]).convert("RGB"), title)
        else:
            print(f"[SKIP] No cover.jpg found for {book_name}")
            return
        back_cover_path = os.path.join(images_path, 'back.jpg')
        if os.path.exists(back_cover_path):
            back_page = centre_crop_image(Image.open(back_cover_path).convert('RGB'))
        else:
            # If no back cover, use a blank page
            back_page = Image.new('RGB', (int(PAGE_SIZE[0]), int(PAGE_SIZE[1])), (255, 255, 255))
        # --- KDP COVER SPREAD ---
        # Create a blank cover spread at KDP-required size
        cover_spread = Image.new('RGB', COVER_SIZE, (255, 255, 255))
        half_width = COVER_SIZE[0] // 2
        height = COVER_SIZE[1]
        # Resize and centre crop images so they completely fill each half of the
        # spread.  This ensures the artwork extends into the bleed area.
        def fill_crop(img, target_w, target_h):
            """Resize and crop an image so it completely fills ``target_w``×``target_h``."""
            size = (int(target_w), int(target_h))
            return ImageOps.fit(img, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))

        back_resized = fill_crop(back_page, half_width, height)
        cover_resized = fill_crop(cover_page, half_width, height)
        # Place the back cover on the left and the front cover on the right
        cover_spread.paste(back_resized, (0, 0))
        cover_spread.paste(cover_resized, (half_width, 0))

        # Add spine text if the book is thick enough
        page_count = len(paragraphs) * 2
        if page_count >= 100:
            spine_width_in = 0.002252 * page_count
            spine_w = int(spine_width_in * DPI)
            spine_x = half_width - spine_w // 2
            spine = Image.new("RGBA", cover_spread.size, (0, 0, 0, 0))
            font = get_heading_font(int(INCH * 0.2))
            text = title
            text_img = Image.new("RGBA", (spine_w, height), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(text_img)
            text_bbox = tdraw.textbbox((0, 0), text, font=font)
            tw = text_bbox[2] - text_bbox[0]
            th = text_bbox[3] - text_bbox[1]
            tx = (spine_w - tw) // 2
            ty = (height - th) // 2
            tdraw.text((tx, ty), text, font=font, fill=(0, 0, 0, 255))
            rotated = text_img.rotate(90, expand=True)
            spine.paste(rotated, (spine_x, 0), rotated)
            cover_spread = Image.alpha_composite(cover_spread.convert("RGBA"), spine).convert("RGB")
        # Save the cover spread as a PDF
        cover_spread.save(cover_pdf, "PDF", resolution=300.0)
        print(f'Cover PDF generated at {cover_pdf}')
    # --- INTERIOR PAGES (MANUSCRIPT) ---
    pages: list[Image.Image] = []
    # Create pages for each paragraph (illustration + text)
    for idx, paragraph in enumerate(paragraphs):
        img_path = image_files[idx + 1]
        if not os.path.exists(img_path):
            print(f"[SKIP] No image for page {idx+1} in {book_name}")
            return
        img = Image.open(img_path).convert('RGB')
        # Determine the page index for the illustration page
        page_idx = len(pages) + 1  # +1 because cover is not included
        # Centre crop the illustration
        pages.append(centre_crop_image(img))
        # Now create the corresponding text page.  Its index will be the
        # current length of pages (image was just appended) + 1
        page_idx = len(pages) + 1
        pages.append(create_text_page(paragraph, page_idx))
    # Save the manuscript PDF (interior pages only)
    if pages:
        pages[0].save(
            output_pdf,
            save_all=True,
            append_images=pages[1:],
            resolution=300.0,
        )
        print(f'Manuscript PDF generated at {output_pdf}')
    else:
        print(f"[SKIP] No interior pages generated for {book_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate picture book PDFs")
    parser.add_argument(
        "-b",
        "--book",
        action="append",
        help="Book folder inside 'books/'. Can be supplied multiple times.",
    )
    parser.add_argument(
        "--skip-cover",
        action="store_true",
        help="Skip generating the cover PDF",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory to place generated PDFs. Defaults to the book folder.",
    )
    args = parser.parse_args()

    if args.book:
        book_names = args.book
    else:
        book_names = [
            d
            for d in os.listdir(BOOKS_DIR)
            if os.path.isdir(os.path.join(BOOKS_DIR, d))
        ]

    for book_name in book_names:
        print(f"Generating book for: {book_name}")
        generate_book(book_name, output_dir=args.output_dir, skip_cover=args.skip_cover)

if __name__ == "__main__":
    main()

import os
import sys
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Constants for KDP 8.5x8.5 inch book at 300 DPI
INCH = 300
PAGE_SIZE = (8.5 * INCH, 8.5 * INCH)  # (width, height) in pixels
FONT_SIZE = 1200  # Increased for maximum readability
MARGIN = 100

# Paths
BOOKS_DIR = 'books'
BOOK_NAME = 'ExampleBook'
BOOK_PATH = os.path.join(BOOKS_DIR, BOOK_NAME)
IMAGES_PATH = os.path.join(BOOK_PATH, 'images')
TEXT_PATH = os.path.join(BOOK_PATH, 'book_text.txt')
OUTPUT_PDF = os.path.join(BOOK_PATH, f'{BOOK_NAME}_output.pdf')

# Load text
with open(TEXT_PATH, 'r') as f:
    content = f.read()
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

# Get images (cover first, then page1, page2, ...)
image_files = [
    os.path.join(IMAGES_PATH, 'cover.jpg')
]
for i in range(1, len(paragraphs) + 1):
    image_files.append(os.path.join(IMAGES_PATH, f'page{i}.jpg'))

# Load a font (fallback to default if not found)
def get_font(size):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except:
            print("Error: No scalable TTF font found. Please install 'DejaVuSans-Bold.ttf' or 'arial.ttf'.")
            sys.exit(1)

font = get_font(FONT_SIZE)

def add_text_to_image(img, text, font, margin):
    draw = ImageDraw.Draw(img)
    # Wrap text
    lines = []
    words = text.split()
    line = ''
    for word in words:
        test_line = f'{line} {word}'.strip()
        w, h = draw.textsize(test_line, font=font)
        if w + 2 * margin > img.width and line:
            lines.append(line)
            line = word
        else:
            line = test_line
    if line:
        lines.append(line)
    # Calculate total text height
    line_heights = [draw.textsize(l, font=font)[1] for l in lines]
    total_h = sum(line_heights) + (len(lines)-1)*10
    # Center vertically
    y = (img.height - total_h) // 2
    for i, l in enumerate(lines):
        w, h = draw.textsize(l, font=font)
        x = (img.width - w) // 2
        draw.text((x, y), l, font=font, fill=(0,0,0))
        y += h + 10
    return img

pages = []
# Cover page (no text)
cover_img = Image.open(image_files[0]).convert('RGB')
cover_img = cover_img.resize((int(PAGE_SIZE[0]), int(PAGE_SIZE[1])))
pages.append(cover_img)

# For each page, add image page (with no text), then text page (text only)
for idx, paragraph in enumerate(paragraphs):
    img_path = image_files[idx + 1]  # page1.jpg, page2.jpg, ...
    # Image page (no text)
    img = Image.open(img_path).convert('RGB')
    img = img.resize((int(PAGE_SIZE[0]), int(PAGE_SIZE[1])))
    pages.append(img)
    # Text page (white background, text centered)
    text_img = Image.new('RGB', (int(PAGE_SIZE[0]), int(PAGE_SIZE[1])), (255, 255, 255))
    text_img = add_text_to_image(text_img, paragraph, font, MARGIN)
    pages.append(text_img)

# Save as PDF
pages[0].save(OUTPUT_PDF, save_all=True, append_images=pages[1:])
print(f'PDF generated at {OUTPUT_PDF}') 
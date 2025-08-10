import os
import argparse
from pathlib import Path
from typing import Optional
import httpx
import base64
import json
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from build_book import generate_book as build_pdf


def log_token_usage(token_file: Path, request_name: str, input_tokens: int, output_tokens: int) -> None:
    """Append token usage information to a file and echo to console."""
    line = f"{request_name}: input_tokens={input_tokens}, output_tokens={output_tokens}\n"
    with token_file.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())


def get_token_counts(resp) -> tuple[int, int]:
    """Extract input and output token counts from an OpenAI response."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    else:
        input_tokens = getattr(usage, "input_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage, "completion_tokens", 0)
    return input_tokens or 0, output_tokens or 0

def generate_image(
    prompt: str,
    out_path: Path,
    client: OpenAI,
    token_file: Path,
    request_name: str,
    reference_image: Optional[Path] = None,
) -> None:
    """Generate an image using gpt-image-1, falling back to a placeholder."""

    input_tokens = output_tokens = 0
    try:
        if reference_image and reference_image.exists():
            with reference_image.open("rb") as rf:
                resp = client.images.edit(
                    image=rf,
                    prompt=prompt,
                    model="gpt-image-1",
                    output_format="jpeg",
                    input_fidelity="high",
                    user="picture-book-generator",
                )
        else:
            resp = client.images.generate(
                prompt=prompt,
                model="gpt-image-1",
                output_format="jpeg",
                user="picture-book-generator",
            )
        input_tokens, output_tokens = get_token_counts(resp)
        img_b64 = resp.data[0].b64_json
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(img_b64))
    except Exception as exc:
        print(f"Image generation failed: {exc}. Using placeholder.")
        save_placeholder_image(prompt, out_path)
    finally:
        log_token_usage(token_file, request_name, input_tokens, output_tokens)


def prompt_user() -> dict:
    """Collect book information from the user, with option to reuse previous prompts."""
    books_dir = Path("books")
    books_dir.mkdir(exist_ok=True)
    existing_books = [d for d in books_dir.iterdir() if d.is_dir() and (d / "prompt.json").exists()]
    info = None
    if existing_books:
        print("Existing books found:")
        for idx, book in enumerate(existing_books, 1):
            print(f"{idx}. {book.name}")
        print(f"{len(existing_books)+1}. Create new book")
        choice = input(f"Select a book to reuse its prompt (1-{len(existing_books)+1}): ")
        try:
            choice = int(choice)
        except ValueError:
            choice = len(existing_books)+1
        if 1 <= choice <= len(existing_books):
            with open(existing_books[choice-1] / "prompt.json", "r", encoding="utf-8") as f:
                info = json.load(f)
                print(f"Loaded prompt for '{info['title']}'")
    if not info:
        title = input("Book title: ")
        topic = input("What is the book about? ")
        
        # Validate page count - minimum 12 pages
        while True:
            try:
                pages = int(input("Number of pages (excluding cover, minimum 12): "))
                if pages < 12:
                    print("Error: Minimum number of pages is 12. Please enter 12 or more pages.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number (minimum 12 pages).")
        
        book_type = input("Story book or rhyming book? (story/rhyme): ")
        style = input("Preferred drawing style: ")
        info = {
            "title": title,
            "topic": topic,
            "pages": pages,
            "book_type": book_type.strip().lower(),
            "style": style,
        }
    # Save prompt to book folder
    book_dir = books_dir / info["title"].replace(" ", "_")
    book_dir.mkdir(parents=True, exist_ok=True)
    with open(book_dir / "prompt.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return info


def get_api_key() -> str:
    key_path = Path(".openai_api_key")
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    api_key = os.getenv("OPENAI_API_KEY") or input("OpenAI API key: ")
    key_path.write_text(api_key.strip(), encoding="utf-8")
    return api_key.strip()


def save_placeholder_image(prompt: str, out_path: Path):
    # Create a simple placeholder image with the prompt text
    img = Image.new('RGB', (1024, 1024), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    lines = []
    words = prompt.split()
    line = ''
    for word in words:
        if len(line + ' ' + word) > 40:
            lines.append(line)
            line = word
        else:
            if line:
                line += ' '
            line += word
    if line:
        lines.append(line)
    y = 50
    for l in lines:
        safe_text = l.encode("ascii", "replace").decode("ascii")
        d.text((50, y), safe_text, fill=(0, 0, 0), font=font)
        y += 30
    img.save(out_path)


def chat_completion(messages, client, token_file: Path, request_name: str, model="gpt-4.1"):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    input_tokens, output_tokens = get_token_counts(response)
    log_token_usage(token_file, request_name, input_tokens, output_tokens)
    return response.choices[0].message.content.strip()


def main(cover_reference: Optional[Path] = None) -> None:
    print("\n========== Picture Book Generator ==========")
    info = prompt_user()

    # Directory setup
    book_dir = Path("books") / info["title"].replace(" ", "_")
    img_dir = book_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    token_file = book_dir / "token_record.txt"
    token_file.write_text("request_name\tinput_tokens\toutput_tokens\n", encoding="utf-8")

    api_key = get_api_key()
    client = OpenAI(api_key=api_key, http_client=httpx.Client())

    # Start persistent chat
    messages = [
        {"role": "system", "content": "You are a helpful assistant for generating children's books. You will be asked to write stories and describe images for illustration. Always keep the story and illustrations consistent."}
    ]

    print("\n[1/7] Generating story text...")
    
    # Generate story text with feedback loop
    prose_or_rhyme = "in rhyming verse" if info["book_type"].startswith("r") else "in prose"
    story_prompt = (
        f"Write a {info['pages']}-page children's book {prose_or_rhyme}. "
        f"The title is '{info['title']}'. "
        f"It is about {info['topic']}. "
        f"Output exactly {info['pages']} paragraphs, one for each page, in order. "
        f"Do not include any page numbers, headers, or extra text. "
        f"Separate each paragraph with a single blank line. "
        f"The output should be ready to save to a text file, with each page's text as a paragraph separated by a blank line."
        f"Please spend your time on generating the story and confirm you are meeting the requirements. "
        f"please use simple words and sentences appropriate for a 3 year old and use simple punctuation."
    )

    print("="*50)
    print("GENERATED STORY PROMPT:")
    print("="*50)
    print(story_prompt)
    print("="*50)
    
    story_satisfied = False
    attempt = 1
    while not story_satisfied:
        messages.append({"role": "user", "content": story_prompt})
        story_text = chat_completion(messages, client, token_file, f"story_attempt_{attempt}")
        attempt += 1
        pages = [p.strip() for p in story_text.split("\n\n") if p.strip()]
        
        # Check if the generated story has the correct number of pages
        if len(pages) != info['pages']:
            print(f"\nError: Generated story has {len(pages)} pages, but {info['pages']} pages were requested.")
            print("Regenerating story with correct page count...")
            continue
        
        # Display the generated story
        print("\n" + "="*50)
        print("GENERATED STORY:")
        print("="*50)
        for i, page in enumerate(pages, 1):
            print(f"\nPage {i}:")
            print(page)
        print("="*50)
        
        # Ask for feedback
        feedback = input("\nAre you happy with this story? (yes/no): ").strip().lower()
        if feedback in ['yes', 'y', '']:
            story_satisfied = True
            print("Great! Continuing with story generation...")
        else:
            user_feedback = input("Please provide feedback for improvements: ").strip()
            if user_feedback:
                # Add feedback to the prompt for the next iteration
                story_prompt = (
                    f"Write a {info['pages']}-page children's book {prose_or_rhyme}. "
                    f"The title is '{info['title']}'. "
                    f"It is about {info['topic']}. "
                    f"Output exactly {info['pages']} paragraphs, one for each page, in order. "
                    f"Do not include any page numbers, headers, or extra text. "
                    f"Separate each paragraph with a single blank line. "
                    f"The output should be ready to save to a text file, with each page's text as a paragraph separated by a blank line. "
                    f"IMPORTANT FEEDBACK TO INCORPORATE: {user_feedback}"
                )
                print("Regenerating story with your feedback...")
            else:
                print("No feedback provided, regenerating story...")
    
    # Save the final story
    (book_dir / "book_text.txt").write_text("\n\n".join(pages), encoding="utf-8")

    print("[2/7] Generating cover image...")
    # Generate cover image description
    cover_prompt = (
        f"Create a cover image for a children's book titled '{info['title']}'. "
        f"The book is about: {info['topic']}. The cover illustration should reflect this subject. "
        f"The story is: {story_text}. "
        f"Style: {info['style']}. The style, characters, and objects must remain consistent throughout the book. "
        f"The images have to be square no matter what as it will go on a 8.5x8.5 children's book cover."
        f"no letters ever touch or overflow the edge. "
        f"LOCKED: main character appearance."
    )
    cover_path = img_dir / "cover.jpg"
    generate_image(cover_prompt, cover_path, client, token_file, "cover_image", reference_image=cover_reference)

    # Generate back cover image
    print("[3/7] Generating back cover image...")
    back_cover_prompt = (
        f"Create a square illustration of the main element from the children's book titled '{info['title']}'. "
        f"The main element may be the main character or a central object, as appropriate for the story. "
        f"The image should be visually appealing, centered, and match the style and theme of the book. "
        f"Style: {info['style']}. The image must be square as if it will go on a 8.5x8.5 children's book back cover. "
        f"Do not include any letters or text."
    )
    back_cover_path = img_dir / "back.jpg"
    generate_image(back_cover_prompt, back_cover_path, client, token_file, "back_cover_image", reference_image=cover_path)

    print("[4/7] Generating title page...")
    
    # Generate title page (page 1) first
    print("    Generating title page image...")
    title_page_prompt = (
        f"Create a title page illustration for the children's book '{info['title']}'. "
        f"This is page 1 - a simple, elegant title page. "
        f"Show the main subject/character from the story in the center of the image. "
        f"Below the main subject, include the book title '{info['title']}' in large, clear text. "
        f"Use the same style as the cover: {info['style']}. "
        f"The style and main character appearance must remain consistent with the cover. "
        f"The image must be square as if it will go in a 8.5x8.5 children's book page. "
        f"Make it clean and simple - just the main subject and title text. "
        f"Using the provided reference image, maintain visual continuity for the main character."
    )
    generate_image(title_page_prompt, img_dir / "page1.jpg", client, token_file, "title_page_image", reference_image=cover_path)
    
    print("[5/7] Generating story page images...")
    # Generate story pages (starting from page 2)
    for i, page_text in enumerate(pages, start=1):
        print(f"    Generating page {i+1} image...")
        page_prompt = (
            f"Create an illustration for page {i+1} of the book '{info['title']}'. "
            f"Use the same style as the cover. {info['style']} "
            f"The style, characters, and objects must remain consistent throughout the book. "
            f"The image must be square as if it will go in a 8.5x8.5 children's book page. "
            f"no letters ever touch or overflow the edge. "
            f"LOCKED: main character appearance. Using the provided reference image, maintain visual continuity. "
            f"The text for this page is: {page_text}"
            f"Please DON'T include any text in the image. as this it printed on a different page."
            f"Also make the images different from each other so keep the style and characters consistent but use different poses, backgrounds, and objects."
        )
        generate_image(page_prompt, img_dir / f"page{i+1}.jpg", client, token_file, f"page_{i+1}_image", reference_image=cover_path)

    print(f"[6/7] Book generation complete!\n  Book directory: {book_dir}\n  Images directory: {img_dir}\n  Story text: {book_dir / 'book_text.txt'}\n")

    print("[7/7] Building final PDF...")
    try:
        build_pdf(book_dir.name)
        print("PDF generation complete.")
    except Exception as exc:
        print(f"Failed to build PDF: {exc}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a children's picture book")
    parser.add_argument(
        "--cover-reference",
        type=Path,
        help="Path to an image used as a reference for the cover",
    )
    args = parser.parse_args()
    ref_img = args.cover_reference
    if ref_img and not ref_img.exists():
        print(f"Reference image {ref_img} not found. Continuing without it.")
        ref_img = None
    main(ref_img)

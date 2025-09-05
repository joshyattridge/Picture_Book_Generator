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

from demo_client import DemoOpenAI


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


def prompt_user() -> tuple[dict, bool, bool]:
    """Collect book information from the user, with option to reuse previous prompts.

    Returns a tuple of (info, regenerate_text, regenerate_images). The regeneration
    choices are not persisted to disk and are asked each run.
    """
    books_dir = Path("books")
    books_dir.mkdir(exist_ok=True)
    existing_books = [d for d in books_dir.iterdir() if d.is_dir() and (d / "prompt.json").exists()]
    info = None
    regenerate_text = True
    regenerate_images = True
    
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
            selected_book_dir = existing_books[choice-1]
            with open(selected_book_dir / "prompt.json", "r", encoding="utf-8") as f:
                info = json.load(f)
                # Ensure transient flags are not carried over from old files
                info.pop("regenerate_text", None)
                info.pop("regenerate_images", None)
                print(f"Loaded prompt for '{info['title']}'")
            
            # Check if existing content is available
            has_existing_text = (selected_book_dir / "book_text.txt").exists()
            has_existing_images = (selected_book_dir / "images").exists() and any((selected_book_dir / "images").glob("*.jpg"))
            
            if has_existing_text:
                print(f"\nExisting story text found in {selected_book_dir / 'book_text.txt'}")
                text_choice = input("Do you want to use existing text or regenerate it? (use/regenerate): ").strip().lower()
                regenerate_text = text_choice not in ['use', 'u', '']
            
            if has_existing_images:
                print(f"\nExisting images found in {selected_book_dir / 'images'}")
                image_choice = input("Do you want to use existing images or regenerate them? (use/regenerate): ").strip().lower()
                regenerate_images = image_choice not in ['use', 'u', '']
    
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
    # Ensure only persistent fields are saved
    info_to_save = dict(info)
    info_to_save.pop("regenerate_text", None)
    info_to_save.pop("regenerate_images", None)
    with open(book_dir / "prompt.json", "w", encoding="utf-8") as f:
        json.dump(info_to_save, f, indent=2)
    return info, regenerate_text, regenerate_images


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


def main(cover_reference: Optional[Path] = None, demo: bool = False) -> None:
    print("\n========== Picture Book Generator ==========")
    if demo:
        print("[DEMO MODE] Using local demo responses and images. No API calls.")
    info, regenerate_text, regenerate_images = prompt_user()

    # Directory setup
    book_dir = Path("books") / info["title"].replace(" ", "_")
    img_dir = book_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    token_file = book_dir / "token_record.txt"
    token_file.write_text("request_name\tinput_tokens\toutput_tokens\n", encoding="utf-8")

    if demo:
        client = DemoOpenAI()
    else:
        api_key = get_api_key()
        client = OpenAI(api_key=api_key, http_client=httpx.Client())

    # Start persistent chat
    messages = [
        {"role": "system", "content": "You are a helpful assistant for generating children's books. You will be asked to write stories and describe images for illustration. Always keep the story and illustrations consistent."}
    ]

    # Handle story text generation or reuse
    if regenerate_text:
        print("\n[1/7] Generating story text...")
        
        # Generate story text with feedback loop
        story_prompt = (
            f"Write a {info['pages']}-page children's book. "
            f"The title is '{info['title']}'. "
            f"It is about {info['topic']}. "
            f"The style should be {info['book_type']}. "
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
                        f"Write a {info['pages']}-page children's book. "
                        f"The title is '{info['title']}'. "
                        f"It is about {info['topic']}. "
                        f"The style should be {info['book_type']}. "
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
    else:
        print("\n[1/7] Using existing story text...")
        # Load existing story text
        existing_text_file = book_dir / "book_text.txt"
        if existing_text_file.exists():
            story_text = existing_text_file.read_text(encoding="utf-8")
            pages = [p.strip() for p in story_text.split("\n\n") if p.strip()]
            print(f"Loaded existing story with {len(pages)} pages")
        else:
            print("Warning: No existing story text found, generating new story...")
            # Fall back to generating new story
            story_prompt = (
                f"Write a {info['pages']}-page children's book. "
                f"The title is '{info['title']}'. "
                f"It is about {info['topic']}. "
                f"The style should be {info['book_type']}. "
                f"Output exactly {info['pages']} paragraphs, one for each page, in order. "
                f"Do not include any page numbers, headers, or extra text. "
                f"Separate each paragraph with a single blank line. "
                f"The output should be ready to save to a text file, with each page's text as a paragraph separated by a blank line."
                f"Please spend your time on generating the story and confirm you are meeting the requirements. "
                f"please use simple words and sentences appropriate for a 3 year old and use simple punctuation."
            )
            messages.append({"role": "user", "content": story_prompt})
            story_text = chat_completion(messages, client, token_file, "story_fallback")
            pages = [p.strip() for p in story_text.split("\n\n") if p.strip()]
            (book_dir / "book_text.txt").write_text("\n\n".join(pages), encoding="utf-8")

    # Handle cover image generation or reuse
    cover_path = img_dir / "cover.jpg"
    if regenerate_images:
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
        generate_image(cover_prompt, cover_path, client, token_file, "cover_image", reference_image=cover_reference)
    else:
        print("[2/7] Using existing cover image...")
        if not cover_path.exists():
            print("Warning: No existing cover image found, generating new one...")
            cover_prompt = (
                f"Create a cover image for a children's book titled '{info['title']}'. "
                f"The book is about: {info['topic']}. The cover illustration should reflect this subject. "
                f"The story is: {story_text}. "
                f"Style: {info['style']}. The style, characters, and objects must remain consistent throughout the book. "
                f"The images have to be square no matter what as it will go on a 8.5x8.5 children's book cover."
                f"no letters ever touch or overflow the edge. "
                f"LOCKED: main character appearance."
            )
            generate_image(cover_prompt, cover_path, client, token_file, "cover_image", reference_image=cover_reference)

    # Handle back cover image generation or reuse
    back_cover_path = img_dir / "back.jpg"
    if regenerate_images:
        print("[3/7] Generating back cover image...")
        back_cover_prompt = (
            f"Create a square illustration of the main element from the children's book titled '{info['title']}'. "
            f"The main element may be the main character or a central object, as appropriate for the story. "
            f"The image should be visually appealing, centered, and match the style and theme of the book. "
            f"Style: {info['style']}. The image must be square as if it will go on a 8.5x8.5 children's book back cover. "
            f"Do not include any letters or text."
        )
        generate_image(back_cover_prompt, back_cover_path, client, token_file, "back_cover_image", reference_image=cover_path)
    else:
        print("[3/7] Using existing back cover image...")
        if not back_cover_path.exists():
            print("Warning: No existing back cover image found, generating new one...")
            back_cover_prompt = (
                f"Create a square illustration of the main element from the children's book titled '{info['title']}'. "
                f"The main element may be the main character or a central object, as appropriate for the story. "
                f"The image should be visually appealing, centered, and match the style and theme of the book. "
                f"Style: {info['style']}. The image must be square as if it will go on a 8.5x8.5 children's book back cover. "
                f"Do not include any letters or text."
            )
            generate_image(back_cover_prompt, back_cover_path, client, token_file, "back_cover_image", reference_image=cover_path)

    # Handle title page generation or reuse
    title_page_path = img_dir / "page1.jpg"
    if regenerate_images:
        print("[4/7] Generating title page...")
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
        generate_image(title_page_prompt, title_page_path, client, token_file, "title_page_image", reference_image=cover_path)
    else:
        print("[4/7] Using existing title page...")
        if not title_page_path.exists():
            print("Warning: No existing title page found, generating new one...")
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
            generate_image(title_page_prompt, title_page_path, client, token_file, "title_page_image", reference_image=cover_path)
    
    # Handle story page images generation or reuse
    if regenerate_images:
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
    else:
        print("[5/7] Using existing story page images...")
        # Check which pages exist and generate missing ones
        for i, page_text in enumerate(pages, start=1):
            page_path = img_dir / f"page{i+1}.jpg"
            if not page_path.exists():
                print(f"    Generating missing page {i+1} image...")
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
                generate_image(page_prompt, page_path, client, token_file, f"page_{i+1}_image", reference_image=cover_path)
            else:
                print(f"    Using existing page {i+1} image...")

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
    parser.add_argument(
        "--demo",
        "-demo",
        action="store_true",
        help="Run in demo mode using local placeholder text and images (no API).",
    )
    args = parser.parse_args()
    ref_img = args.cover_reference
    if ref_img and not ref_img.exists():
        print(f"Reference image {ref_img} not found. Continuing without it.")
        ref_img = None
    main(ref_img, demo=args.demo)

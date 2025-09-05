import argparse
from pathlib import Path
from typing import Optional
import httpx
import base64
import json
from openai import OpenAI
# PIL not required here anymore; demo image gen lives in demo_client.py
from build_book import generate_book as build_pdf

from demo_client import DemoOpenAI

def generate_image(
    prompt: str,
    out_path: Path,
    client: OpenAI,
    reference_image: Optional[Path] = None,
) -> None:
    """Generate an image using gpt-image-1, falling back to a placeholder."""

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
        img_b64 = resp.data[0].b64_json
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(img_b64))
    except Exception as exc:
        print(f"Image generation failed: {exc}.")
        raise SystemExit(1)

def chat_completion(messages, client, model="gpt-4.1"):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content.strip()


def main(
    cover_reference: Optional[Path] = None,
    demo: bool = False,
    title: Optional[str] = None,
    topic: Optional[str] = None,
    pages: Optional[int] = None,
    book_type: Optional[str] = None,
    style: Optional[str] = None,
    api_key: Optional[str] = None,
) -> None:
    print("\n========== Picture Book Generator ==========")
    if demo:
        print("[DEMO MODE] Using local demo responses and images. No API calls.")
    # Validate required fields and build info from CLI args only
    missing = [
        n for n, v in [
            ("--title", title),
            ("--topic", topic),
            ("--pages", pages),
            ("--book-type", book_type),
            ("--style", style),
        ]
        if v in (None, "")
    ]
    if missing:
        raise SystemExit("Missing required arguments: " + ", ".join(missing))
    if int(pages) < 12:
        raise SystemExit("--pages must be at least 12")

    info = {
        "title": title,
        "topic": topic,
        "pages": int(pages),
        "book_type": (book_type or "").strip().lower(),
        "style": style,
    }

    # Directories (no prompt.json persistence)
    book_dir = Path("books") / info["title"].replace(" ", "_")
    book_dir.mkdir(parents=True, exist_ok=True)
    img_dir = book_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # No token recording file

    if demo:
        client = DemoOpenAI()
    else:
        if not api_key:
            raise SystemExit("Missing --api-key (required unless running with --demo).")
        client = OpenAI(api_key=api_key.strip(), http_client=httpx.Client())

    # Start persistent chat
    messages = [
        {"role": "system", "content": "You are a helpful assistant for generating children's books. You will be asked to write stories and describe images for illustration. Always keep the story and illustrations consistent."}
    ]

    # Generate story text
    print("\n[1/7] Generating story text...")
    # Generate story text and confirm acceptance interactively once
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

    attempt = 1
    while True:
        messages.append({"role": "user", "content": story_prompt})
        story_text = chat_completion(messages, client)
        pages = [p.strip() for p in story_text.split("\n\n") if p.strip()]
        if len(pages) == info['pages']:
            break
        print(f"\nError: Generated story has {len(pages)} pages, but {info['pages']} were requested. Regenerating...")
        attempt += 1

    # Display the generated story
    print("\n" + "="*50)
    print("GENERATED STORY:")
    print("="*50)
    for i, page in enumerate(pages, 1):
        print(f"\nPage {i}:")
        print(page)
    print("="*50)

    # Ask for acceptance; if rejected, exit without saving or continuing
    feedback = input("\nAre you happy with this story? (yes/no): ").strip().lower()
    if feedback not in ['yes', 'y', '']:
        print("Exiting without saving. Re-run to try again.")
        raise SystemExit(1)

    # Save the accepted story
    (book_dir / "book_text.txt").write_text("\n\n".join(pages), encoding="utf-8")

    # Handle cover image generation
    cover_path = img_dir / "cover.jpg"
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
    generate_image(cover_prompt, cover_path, client, reference_image=cover_reference)

    # Handle back cover image generation
    back_cover_path = img_dir / "back.jpg"
    print("[3/7] Generating back cover image...")
    back_cover_prompt = (
        f"Create a square illustration of the main element from the children's book titled '{info['title']}'. "
        f"The main element may be the main character or a central object, as appropriate for the story. "
        f"The image should be visually appealing, centered, and match the style and theme of the book. "
        f"Style: {info['style']}. The image must be square as if it will go on a 8.5x8.5 children's book back cover. "
        f"Do not include any letters or text."
    )
    generate_image(back_cover_prompt, back_cover_path, client, reference_image=cover_path)

    # Handle title page generation
    title_page_path = img_dir / "page1.jpg"
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
    generate_image(title_page_prompt, title_page_path, client, reference_image=cover_path)
    
    # Handle story page images generation (always regenerate)
    print("[5/7] Generating story page images...")
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
        generate_image(page_prompt, img_dir / f"page{i+1}.jpg", client, reference_image=cover_path)

    print(f"[6/7] Book generation complete!\n  Book directory: {book_dir}\n  Images directory: {img_dir}\n  Story text: {book_dir / 'book_text.txt'}\n")

    print("[7/7] Building final PDF...")
    try:
        build_pdf(book_dir.name)
        print("PDF generation complete.")
    except Exception as exc:
        print(f"Failed to build PDF: {exc}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generate a children's picture book from the command line. "
            "Provide --title/--topic/--pages/--book-type/--style for each run. "
            "The script always regenerates text and images."
        )
    )

    # Book details (no persistence/reuse)
    parser.add_argument("--title", type=str, help="Book title (used to create folder name)")
    parser.add_argument("--topic", type=str, help="What the book is about")
    parser.add_argument(
        "--pages",
        type=int,
        help="Number of story pages (minimum 12; excludes cover and back)",
    )
    parser.add_argument(
        "--book-type",
        type=str,
        help="Type of book: e.g., 'story' or 'rhyme' (free text)",
    )
    parser.add_argument("--style", type=str, help="Preferred illustration style (free text)")
    parser.add_argument(
        "--cover-reference",
        type=Path,
        help="Path to an image used as a visual reference for the cover and character consistency",
    )
    parser.add_argument(
        "--demo",
        "-demo",
        action="store_true",
        help="Run in demo mode using local placeholder text and images (no API).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API key (required unless --demo is used).",
    )

    args = parser.parse_args()

    ref_img = args.cover_reference
    if ref_img and not ref_img.exists():
        print(f"Reference image {ref_img} not found. Continuing without it.")
        ref_img = None

    # Enforce API key requirement when not in demo mode
    if not args.demo and not args.api_key:
        raise SystemExit("--api-key is required when not running with --demo")

    main(
        cover_reference=ref_img,
        demo=args.demo,
        title=args.title,
        topic=args.topic,
        pages=args.pages,
        book_type=args.book_type,
        style=args.style,
        api_key=args.api_key,
    )

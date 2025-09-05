import argparse
from pathlib import Path
from typing import Optional
import httpx
import base64
import json
from openai import OpenAI
# PIL not required here anymore; demo image gen lives in demo_client.py
from build_book import generate_book as build_pdf
from concurrent.futures import ThreadPoolExecutor, as_completed
from prompts import (
    make_story_prompt,
    make_cover_prompt,
    make_back_cover_prompt,
    make_title_page_prompt,
    make_page_prompt,
)

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
    story_prompt = make_story_prompt(info)
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
    cover_prompt = make_cover_prompt(info, story_text)
    generate_image(cover_prompt, cover_path, client, reference_image=cover_reference)

    # Generate title page, back cover, and story page images in parallel
    back_cover_path = img_dir / "back.jpg"
    title_page_path = img_dir / "page1.jpg"
    print("[3/7] Generating images (title, back cover, and story pages)...")
    max_workers = min(8, (len(pages) if pages else 0) + 2)
    if max_workers <= 0:
        print("    No pages to illustrate.")
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Queue title page
            print("    Generating title page image...")
            title_page_prompt = make_title_page_prompt(info)
            fut_title = executor.submit(
                generate_image, title_page_prompt, title_page_path, client, cover_path
            )
            futures[fut_title] = ("title", None)

            # Queue back cover
            print("    Generating back cover image...")
            back_cover_prompt = make_back_cover_prompt(info)
            fut_back = executor.submit(
                generate_image, back_cover_prompt, back_cover_path, client, cover_path
            )
            futures[fut_back] = ("back", None)

            # Queue story pages (starting from page 2)
            for i, page_text in enumerate(pages, start=1):
                print(f"    Generating page {i+1} image...")
                page_prompt = make_page_prompt(info, i, page_text)
                out_path = img_dir / f"page{i+1}.jpg"
                fut = executor.submit(generate_image, page_prompt, out_path, client, cover_path)
                futures[fut] = ("page", i)

            # Handle completions
            for fut in as_completed(futures):
                kind, idx = futures[fut]
                try:
                    fut.result()
                except SystemExit:
                    # Propagate fail-fast behavior if any image generation fails
                    raise
                except Exception as exc:
                    if kind == "page":
                        print(f"    Page {idx+1} image failed: {exc}")
                    else:
                        print(f"    {kind.capitalize()} image failed: {exc}")
                    raise SystemExit(1)
                else:
                    if kind == "page":
                        print(f"    Page {idx+1} image generated.")
                    else:
                        print(f"    {kind.capitalize()} image generated.")

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

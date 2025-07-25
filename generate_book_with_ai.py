import os
from pathlib import Path
from typing import Optional
import openai
import httpx
import base64
import json
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont


def generate_dalle_image(
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
                    size="1024x1024",
                    input_fidelity="high",
                    user="picture-book-generator",
                )
        else:
            resp = client.images.generate(
                prompt=prompt,
                model="gpt-image-1",
                output_format="jpeg",
                size="1024x1024",
                user="picture-book-generator",
            )
        img_b64 = resp.data[0].b64_json
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(img_b64))
    except Exception as exc:
        print(f"Image generation failed: {exc}. Using placeholder.")
        save_placeholder_image(prompt, out_path)


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
        pages = int(input("Number of pages (excluding cover): "))
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


def chat_completion(messages, client, model="gpt-4o"):
    response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    info = prompt_user()

    # Directory setup
    book_dir = Path("books") / info["title"].replace(" ", "_")
    img_dir = book_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    api_key = get_api_key()
    client = OpenAI(api_key=api_key, http_client=httpx.Client())

    # Start persistent chat
    messages = [
        {"role": "system", "content": "You are a helpful assistant for generating children's books. You will be asked to write stories and describe images for illustration. Always keep the story and illustrations consistent."}
    ]

    # Generate story text
    prose_or_rhyme = "in rhyming verse" if info["book_type"].startswith("r") else "in prose"
    story_prompt = (
        f"Write a {info['pages']}-page children's book {prose_or_rhyme}. "
        f"The title is '{info['title']}'. "
        f"It is about {info['topic']}. "
        f"Output exactly {info['pages']} paragraphs, one for each page, in order. "
        f"Do not include any page numbers, headers, or extra text. "
        f"Separate each paragraph with a single blank line. "
        f"The output should be ready to save to a text file, with each page's text as a paragraph separated by a blank line."
    )
    messages.append({"role": "user", "content": story_prompt})
    story_text = chat_completion(messages, client)
    messages.append({"role": "assistant", "content": story_text})
    pages = [p.strip() for p in story_text.split("\n\n") if p.strip()]
    (book_dir / "book_text.txt").write_text("\n\n".join(pages), encoding="utf-8")

    # Generate cover image description
    cover_prompt = (
        f"Describe a cover illustration for a children's book titled '{info['title']}'. "
        f"Style: {info['style']}. Keep all characters and objects consistent for the rest of the book. "
        f"LOCKED: main character appearance."
    )
    messages.append({"role": "user", "content": cover_prompt})
    cover_desc = chat_completion(messages, client)
    messages.append({"role": "assistant", "content": cover_desc})
    cover_path = img_dir / "cover.jpg"
    generate_dalle_image(cover_desc, cover_path, client)
    with cover_path.open("rb") as cf:
        cover_b64 = base64.b64encode(cf.read()).decode("utf-8")

    # Generate page image descriptions referencing the cover for character consistency
    for i, page_text in enumerate(pages, start=1):
        page_prompt = (
            f"Describe an illustration for page {i} of the book '{info['title']}'. "
            f"Use the same characters and style as the cover. {info['style']} "
            f"LOCKED: main character appearance. Using the provided reference image, maintain visual continuity. "
            f"The text for this page is: {page_text}"
        )
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": page_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{cover_b64}"}},
            ],
        })
        page_desc = chat_completion(messages, client)
        messages.append({"role": "assistant", "content": page_desc})
        generate_dalle_image(page_desc, img_dir / f"page{i}.jpg", client, reference_image=cover_path)

    print(f"Generated book content in {book_dir}")


if __name__ == "__main__":
    main()

import os
from pathlib import Path
import openai
import base64


def prompt_user() -> dict:
    """Collect book information from the user."""
    title = input("Book title: ")
    topic = input("What is the book about? ")
    pages = int(input("Number of pages (excluding cover): "))
    book_type = input("Story book or rhyming book? (story/rhyme): ")
    style = input("Preferred drawing style: ")
    return {
        "title": title,
        "topic": topic,
        "pages": pages,
        "book_type": book_type.strip().lower(),
        "style": style,
    }


def generate_story(info: dict) -> list[str]:
    """Use OpenAI to create page text for the book."""
    prose_or_rhyme = "in rhyming verse" if info["book_type"].startswith("r") else "in prose"
    prompt = (
        f"Write a {info['pages']}-page children's book {prose_or_rhyme}. "
        f"The title is '{info['title']}'. "
        f"It is about {info['topic']}. "
        f"Provide {info['pages']} separate paragraphs, one for each page."
    )
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    text = completion.choices[0].message.content.strip()
    # Split paragraphs - assume blank lines separate pages
    pages = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(pages) != info["pages"]:
        pages = text.splitlines()
    return pages


def generate_image(prompt: str, out_path: Path) -> None:
    """Generate an image using the OpenAI image API and save it."""
    response = openai.Image.create(prompt=prompt, n=1, size="1024x1024")
    img_data = response["data"][0]["b64_json"]
    out_path.write_bytes(base64.b64decode(img_data))


def main() -> None:
    info = prompt_user()

    # Directory setup
    book_dir = Path("books") / info["title"].replace(" ", "_")
    img_dir = book_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    openai.api_key = os.getenv("OPENAI_API_KEY") or input("OpenAI API key: ")

    # Generate story text
    pages = generate_story(info)
    (book_dir / "book_text.txt").write_text("\n\n".join(pages), encoding="utf-8")

    # Generate cover image
    cover_prompt = (
        f"Cover illustration for a children's book titled '{info['title']}'. "
        f"Style: {info['style']}. Keep all characters and objects consistent for the rest of the book." 
    )
    generate_image(cover_prompt, img_dir / "cover.jpg")

    # Generate page images referencing the cover
    for i, _ in enumerate(pages, start=1):
        page_prompt = (
            f"Illustration for page {i} of the book '{info['title']}'. "
            f"Use the same characters and style as the cover. {info['style']}"
        )
        generate_image(page_prompt, img_dir / f"page{i}.jpg")

    print(f"Generated book content in {book_dir}")


if __name__ == "__main__":
    main()

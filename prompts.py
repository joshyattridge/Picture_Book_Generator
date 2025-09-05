from typing import Dict


def make_story_prompt(info: Dict) -> str:
    return (
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


def make_cover_prompt(info: Dict, story_text: str) -> str:
    return (
        f"Create a cover image for a children's book titled '{info['title']}'. "
        f"The book is about: {info['topic']}. The cover illustration should reflect this subject. "
        f"The story is: {story_text}. "
        f"Style: {info['style']}. The style, characters, and objects must remain consistent throughout the book. "
        f"The images have to be square no matter what as it will go on a 8.5x8.5 children's book cover."
        f"no letters ever touch or overflow the edge. "
        f"LOCKED: main character appearance."
    )


def make_back_cover_prompt(info: Dict) -> str:
    return (
        f"Create a square illustration of the main element from the children's book titled '{info['title']}'. "
        f"The main element may be the main character or a central object, as appropriate for the story. "
        f"The image should be visually appealing, centered, and match the style and theme of the book. "
        f"Style: {info['style']}. The image must be square as if it will go on a 8.5x8.5 children's book back cover. "
        f"Do not include any letters or text."
    )


def make_title_page_prompt(info: Dict) -> str:
    return (
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


def make_page_prompt(info: Dict, page_index: int, page_text: str) -> str:
    i = page_index
    return (
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


import base64
import io
import re
from PIL import Image, ImageDraw, ImageFont


class DemoMessage:
    def __init__(self, content: str):
        self.content = content


class DemoChoice:
    def __init__(self, content: str):
        self.message = DemoMessage(content)


class DemoChatResponse:
    def __init__(self, content: str):
        self.choices = [DemoChoice(content)]
        self.usage = {"input_tokens": 0, "output_tokens": 0}


class DemoImageDatum:
    def __init__(self, b64_json: str):
        self.b64_json = b64_json


class DemoImageResponse:
    def __init__(self, b64_json: str):
        self.data = [DemoImageDatum(b64_json)]
        self.usage = {"input_tokens": 0, "output_tokens": 0}


def _demo_story_from_prompt(prompt_text: str) -> str:
    """Generate simple multi-paragraph demo story text based on requested pages."""
    m = re.search(r"(\d+)[- ]?page|exactly (\d+) paragraphs", prompt_text, re.IGNORECASE)
    pages = 12
    if m:
        pages = int(next(g for g in m.groups() if g))
    return "\n\n".join([f"This is demo text for page {i}." for i in range(1, pages + 1)])


def _demo_image_b64(prompt_text: str) -> str:
    """Create a simple placeholder JPEG and return as base64 string."""
    img = Image.new("RGB", (1024, 1024), color=(240, 240, 240))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    title = "DEMO IMAGE"
    d.text((40, 40), title, fill=(0, 0, 0), font=font)
    snippet = (prompt_text or "").strip().replace("\n", " ")[:80]
    try:
        small_font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        small_font = ImageFont.load_default()
    d.text((40, 110), snippet, fill=(0, 0, 0), font=small_font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


class DemoChatCompletions:
    def create(self, model: str, messages: list):
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        content = _demo_story_from_prompt(last_user)
        return DemoChatResponse(content)


class DemoImages:
    def generate(self, prompt: str, model: str, output_format: str, user: str):
        return DemoImageResponse(_demo_image_b64(prompt))

    def edit(self, image, prompt: str, model: str, output_format: str, input_fidelity: str, user: str):
        return DemoImageResponse(_demo_image_b64(prompt))


class DemoOpenAI:
    def __init__(self, *_, **__):
        self.chat = type("Chat", (), {"completions": DemoChatCompletions()})()
        self.images = DemoImages()


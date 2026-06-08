"""کپچای تصویری — مسئله ریاضی با ۴ گزینه."""
import random
from io import BytesIO

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False


def generate_captcha():
    """
    Returns (image: BytesIO|None, correct_answer: int, choices: list[int])
    choices دارای ۴ عدد است، یکی از آن‌ها correct_answer.
    """
    op = random.choice(['+', '-', '×'])
    if op == '+':
        a, b = random.randint(3, 20), random.randint(3, 20)
        answer = a + b
    elif op == '-':
        a = random.randint(10, 30)
        b = random.randint(1, a - 1)
        answer = a - b
    else:
        a, b = random.randint(2, 9), random.randint(2, 9)
        answer = a * b

    question = f"{a} {op} {b} = ?"

    wrongs: set = set()
    for _ in range(60):
        if len(wrongs) >= 3:
            break
        delta = random.choice([-8, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 8])
        w = answer + delta
        if w > 0 and w != answer:
            wrongs.add(w)

    choices = [answer] + list(wrongs)[:3]
    random.shuffle(choices)

    if not _PIL:
        return None, answer, choices

    W, H = 360, 130
    img = Image.new('RGB', (W, H), (10, 10, 25))
    draw = ImageDraw.Draw(img)

    for _ in range(400):
        x, y = random.randint(0, W - 1), random.randint(0, H - 1)
        draw.point((x, y), fill=(
            random.randint(20, 70),
            random.randint(20, 70),
            random.randint(80, 150),
        ))

    for _ in range(7):
        draw.line([
            (random.randint(0, W), random.randint(0, H)),
            (random.randint(0, W), random.randint(0, H)),
        ], fill=(
            random.randint(30, 90),
            random.randint(30, 90),
            random.randint(90, 160),
        ), width=1)

    font = _load_font(54)

    try:
        bbox = draw.textbbox((0, 0), question, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = font.getsize(question) if font else (200, 50)

    x = (W - tw) // 2
    y = (H - th) // 2

    for dx in (-2, -1, 1, 2):
        for dy in (-2, -1, 1, 2):
            draw.text((x + dx, y + dy), question, font=font, fill=(0, 40, 100))
    draw.text((x, y), question, font=font, fill=(0, 210, 255))
    draw.rectangle([(2, 2), (W - 3, H - 3)], outline=(0, 100, 210), width=2)

    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf, answer, choices


def _load_font(size: int):
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    )
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None

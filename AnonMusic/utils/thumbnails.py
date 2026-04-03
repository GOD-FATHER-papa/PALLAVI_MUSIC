# Copyright (c) 2026 Vibe-Bots

import os
import re
import random
import aiofiles
import aiohttp

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from py_yt import VideosSearch

from config import YOUTUBE_IMG_URL

os.makedirs("cache", exist_ok=True)


# ==============================
# TEXT
# ==============================
def truncate(text, max_len=32):
    words = text.split()
    lines = ["", ""]
    i = 0

    for word in words:
        if len(lines[i]) + len(word) + 1 <= max_len:
            lines[i] += (" " if lines[i] else "") + word
        elif i == 0:
            i = 1
            lines[i] += word
        else:
            break

    return lines


def random_color():
    return tuple(random.randint(120, 255) for _ in range(3))


# ==============================
# IMAGE HELPERS
# ==============================
def circular_crop(img, size, border):
    inner = size - 2 * border
    img = img.resize((inner, inner), Image.LANCZOS)

    mask = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, inner, inner), fill=255)

    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(img, (border, border), mask)

    return output


def draw_text(draw, pos, text, font, fill):
    x, y = pos
    draw.text((x+3, y+3), text, font=font, fill=(0,0,0,180))
    draw.text((x, y), text, font=font, fill=fill)


def gen_gradient(size):
    return Image.linear_gradient("L").resize(size)


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


# ==============================
# MAIN FUNCTION
# ==============================
async def gen_thumb(videoid: str, user_name: str = "Unknown", thumb_size=(1280, 720)):
    path = f"cache/{videoid}.png"

    if os.path.exists(path):
        return path

    temp_path = f"cache/temp_{videoid}.png"

    try:
        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        title = re.sub(r"\W+", " ", data.get("title", "Unknown")).title()
        duration = data.get("duration") or "00:00"
        views = data.get("viewCount", {}).get("short", "0 Views")

        thumb_url = data["thumbnails"][0]["url"].split("?")[0]

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                if resp.status != 200:
                    return YOUTUBE_IMG_URL
                content = await resp.read()

        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(content)

        base = Image.open(temp_path).convert("RGBA")
        base.thumbnail(thumb_size, Image.Resampling.LANCZOS)

        # BACKGROUND
        bg = base.filter(ImageFilter.GaussianBlur(30))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)

        gradient = Image.new("RGBA", thumb_size, random_color())
        mask = gen_gradient(thumb_size)
        bg.paste(gradient, (0, 0), mask)

        draw = ImageDraw.Draw(bg)

        # Fonts
        font_title = load_font("AnonMusic/assets/font3.ttf", 52)
        font_small = load_font("AnonMusic/assets/font2.ttf", 30)
        font_watermark = load_font("AnonMusic/assets/font2.ttf", 24)

        # Circle image
        circle = circular_crop(base, 420, 10)
        bg.paste(circle, (120, 150), circle)

        # TITLE
        x = 580
        t1, t2 = truncate(title)

        draw_text(draw, (x, 170), t1, font_title, "white")
        draw_text(draw, (x, 240), t2, font_title, "white")

        # INFO BLOCK
        info_text = (
            f"YouTube | {views}\n"
            f"Duration | {duration}\n"
            f"Player | @{Kritiprobot}"
        )

        draw.multiline_text((x+2, 332), info_text, font=font_small, fill=(0,0,0,150), spacing=8)
        draw.multiline_text((x, 330), info_text, font=font_small, fill=(180,255,0), spacing=8)

        # PROGRESS BAR
        y = 440
        pct = random.uniform(0.3, 0.9)
        length = int(600 * pct)

        color = random_color()

        draw.line((x, y, x+600, y), fill=(80,80,80), width=8)
        draw.line((x, y, x+length, y), fill=color, width=10)
        draw.ellipse((x+length-8, y-8, x+length+8, y+8), fill=color)

        # Time
        draw_text(draw, (x, 470), "00:00", font_small, "white")
        draw_text(draw, (x+520, 470), duration, font_small, "white")

        # WATERMARKS
        draw.text((22, 682), "GitHub @kirtiBots", font=font_watermark, fill=(0,0,0,150))
        draw.text((20, 680), "GitHub @kirtiBots", font=font_watermark, fill=(0,255,120))

        right_text = "Powered by Kriti-Bots"
        bbox = draw.textbbox((0,0), right_text, font=font_watermark)
        rw = bbox[2]

        rx = thumb_size[0] - rw - 20
        ry = 680

        draw.text((rx+2, ry+2), right_text, font=font_watermark, fill=(0,0,0,150))
        draw.text((rx, ry), right_text, font=font_watermark, fill=(180,255,0))

        # ==============================
        # ✅ WHITE BORDER (NEW)
        # ==============================
        border_size = 8
        final = Image.new(
            "RGB",
            (thumb_size[0] + border_size*2, thumb_size[1] + border_size*2),
            "white"
        )
        final.paste(bg, (border_size, border_size))

        final.save(path)
        return path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL

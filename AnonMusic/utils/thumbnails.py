# Copyright (c) 2026 Vibe-Bots

import os
import re
import random
import aiofiles
import aiohttp

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from py_yt import VideosSearch

from config import YOUTUBE_IMG_URL

# Ensure cache dir exists
os.makedirs("cache", exist_ok=True)


# ==============================
# TEXT HANDLING
# ==============================
def truncate(text, max_len=30):
    words = text.split()
    lines = ["", ""]
    i = 0

    for word in words:
        if len(lines[i]) + len(word) + 1 <= max_len:
            lines[i] += (" " if lines[i] else "") + word
        elif i == 0:
            i = 1
            lines[i] += word

    return lines


def random_color():
    return tuple(random.randint(100, 255) for _ in range(3))


# ==============================
# IMAGE HELPERS
# ==============================
def circular_crop(img, size, border, color):
    inner = size - 2 * border

    img = img.resize((inner, inner), Image.LANCZOS)

    mask = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, inner, inner), fill=255)

    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(img, (border, border), mask)

    return output


def draw_text(draw, pos, text, font, fill):
    x, y = pos
    draw.text((x + 2, y + 2), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill=fill)


def gen_gradient(size, start, end):
    base = Image.new("RGBA", size, start)
    top = Image.new("RGBA", size, end)
    mask = Image.linear_gradient("L").resize(size)
    base.paste(top, (0, 0), mask)
    return base


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


# ==============================
# MAIN THUMB FUNCTION
# ==============================
async def gen_thumb(videoid: str, thumb_size=(1280, 720)):
    path = f"cache/{videoid}.png"

    if os.path.isfile(path):
        return path

    try:
        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        title = re.sub(r"\W+", " ", data.get("title", "Unknown")).title()
        duration = data.get("duration") or "00:00"
        views = data.get("viewCount", {}).get("short", "Unknown Views")
        channel = data.get("channel", {}).get("name", "Unknown Channel")

        thumb_url = data["thumbnails"][0]["url"].split("?")[0]

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                content = await resp.read()

        temp_path = f"cache/temp_{videoid}.png"
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(content)

        base_img = Image.open(temp_path).convert("RGBA")
        base_img.thumbnail(thumb_size, Image.Resampling.LANCZOS)

        # Background
        bg = base_img.filter(ImageFilter.GaussianBlur(25))
        bg = ImageEnhance.Brightness(bg).enhance(0.5)

        gradient = gen_gradient(thumb_size, random_color(), random_color())
        bg = Image.blend(bg, gradient, 0.25)

        draw = ImageDraw.Draw(bg)

        # Fonts
        font_small = load_font("AnonMusic/assets/font2.ttf", 28)
        font_title = load_font("AnonMusic/assets/font3.ttf", 48)
        font_watermark = load_font("AnonMusic/assets/font2.ttf", 24)

        # Circle Image
        circle = circular_crop(base_img, 400, 10, random_color())
        bg.paste(circle, (120, 160), circle)

        # Text
        x = 560
        t1, t2 = truncate(title)

        draw_text(draw, (x, 170), t1, font_title, "white")
        draw_text(draw, (x, 230), t2, font_title, "white")
        draw_text(draw, (x, 310), f"{channel} • {views}", font_small, "white")

        # Progress Bar
        y = 380
        pct = random.uniform(0.2, 0.85)
        length = int(580 * pct)

        bar_color = random_color()

        draw.line((x, y, x + length, y), fill=bar_color, width=10)
        draw.line((x + length, y, x + 580, y), fill="white", width=8)
        draw.ellipse((x + length - 10, y - 10, x + length + 10, y + 10), fill=bar_color)

        # Time
        draw_text(draw, (x, 400), "00:00", font_small, "white")
        draw_text(draw, (1080, 400), duration, font_small, "white")

        # Icons
        try:
            icons = Image.open("AnonMusic/assets/play_icons.png").convert("RGBA")
            bg.paste(icons, (x, 450), icons)
        except:
            pass

        # ==============================
        # DOUBLE WATERMARK
        # ==============================

        # LEFT
        left_text = "Powered by kirti-Bots"
        bbox1 = draw.textbbox((0, 0), left_text, font=font_watermark)
        lw = bbox1[2] - bbox1[0]
        lh = bbox1[3] - bbox1[1]

        lx = 20
        ly = thumb_size[1] - lh - 20

        draw.text((lx+1, ly+1), left_text, font=font_watermark, fill=(0,0,0,150))
        draw.text((lx, ly), left_text, font=font_watermark, fill=(255,255,255,180))

        # RIGHT
        right_text = "Powered by Kriti-Bots"
        bbox2 = draw.textbbox((0, 0), right_text, font=font_watermark)
        rw = bbox2[2] - bbox2[0]
        rh = bbox2[3] - bbox2[1]

        rx = thumb_size[0] - rw - 20
        ry = thumb_size[1] - rh - 20

        draw.text((rx+1, ry+1), right_text, font=font_watermark, fill=(0,0,0,150))
        draw.text((rx, ry), right_text, font=font_watermark, fill=(255,255,255,180))

        # Save
        bg.save(path)
        os.remove(temp_path)

        return path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL

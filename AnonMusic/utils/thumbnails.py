import os, re, random, aiofiles, aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from AnonMusic import app

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ───────────────────────────────────────────────

def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_width:
        return text
    for i in range(len(text), 0, -1):
        new = text[:i] + ellipsis
        if font.getlength(new) <= max_width:
            return new
    return ellipsis

# ───────────────────────────────────────────────

async def get_thumb(videoid: str, player_username: str = None) -> str:
    if player_username is None:
        player_username = app.username

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_thumb.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        search_result = await results.next()
        data = search_result.get("result", [])[0]

        title = data.get("title", "Unknown Title")
        artist = data.get("channel", {}).get("name", "Unknown Artist")
        duration = data.get("duration", "00:00")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)

    except Exception:
        title = "Unknown Title"
        artist = "Unknown Artist"
        duration = "03:00"
        thumbnail = YOUTUBE_IMG_URL

    thumb_path = os.path.join(CACHE_DIR, f"raw_{videoid}.jpg")

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(thumbnail) as r:
                if r.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await r.read())
    except:
        return YOUTUBE_IMG_URL

    W, H = 1280, 720
    base = Image.new("RGB", (W, H), (240, 240, 240))
    draw = ImageDraw.Draw(base)

    # Fonts
    try:
        title_font = ImageFont.truetype("AnonMusic/assets/font2.ttf", 55)
        artist_font = ImageFont.truetype("AnonMusic/assets/font.ttf", 35)
        small_font = ImageFont.truetype("AnonMusic/assets/font.ttf", 30)
    except:
        title_font = artist_font = small_font = ImageFont.load_default()

    # Album Art
    try:
        img = Image.open(thumb_path).resize((500, 500))
    except:
        img = Image.new("RGB", (500, 500), (100, 100, 100))

    base.paste(img, (100, 110))

    # Text
    title = trim_to_width(title, title_font, 500)
    draw.text((700, 200), title, font=title_font, fill=(20, 20, 20))
    draw.text((700, 270), artist, font=artist_font, fill=(80, 80, 80))
    draw.text((700, 320), f"Player: {player_username}", font=small_font, fill=(120, 120, 120))

    # Simple Progress Bar
    draw.line((700, 500, 1100, 500), fill=(180, 180, 180), width=6)
    draw.line((700, 500, 900, 500), fill=(50, 50, 50), width=6)

    # Cleanup
    try:
        os.remove(thumb_path)
    except:
        pass

    base.save(cache_path)
    return cache_path

# ───────────────────────────────────────────────
# 🔥 IMPORTANT ALIASES (NO ERROR GUARANTEE)

gen_thumb = get_thumb
generate_thumb = get_thumb

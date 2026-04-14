import os, re, random, aiofiles, aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from AnonMusic import app

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_width:
        return text
    for i in range(len(text), 0, -1):
        new = text[:i] + ellipsis
        if font.getlength(new) <= max_width:
            return new
    return ellipsis

async def get_thumb(videoid: str, player_username: str = None) -> str:
    if player_username is None:
        player_username = app.username

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_shiv_thumb.png")
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
        duration = "03:27"
        thumbnail = YOUTUBE_IMG_URL

    thumb_path = os.path.join(CACHE_DIR, f"thumb_{videoid}.jpg")

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(thumbnail) as r:
                if r.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await r.read())
    except:
        return YOUTUBE_IMG_URL

    W, H = 1280, 720
    base = Image.new("RGBA", (W, H), (225, 225, 225, 255)) 
    draw = ImageDraw.Draw(base)

    try:
        shiv_bold = "AnonMusic/assets/font2.ttf"
        shukla_reg = "AnonMusic/assets/font.ttf"
        title_font = ImageFont.truetype(shiv_bold, 55)
        artist_font = ImageFont.truetype(shukla_reg, 35)
        player_font = ImageFont.truetype(shiv_bold, 30)
        time_font = ImageFont.truetype(shukla_reg, 40)
    except:
        title_font = artist_font = player_font = time_font = ImageFont.load_default()

    vinyl_size = 480
    vinyl = Image.new("RGBA", (vinyl_size, vinyl_size), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vinyl)
    v_draw.ellipse((0, 0, vinyl_size, vinyl_size), fill=(15, 15, 15, 255))
    
    base.paste(vinyl, (250, (H - vinyl_size) // 2), vinyl)

    raw_img = Image.open(thumb_path).convert("RGBA")
    cover_size = 530
    cover_x, cover_y = 100, (H - cover_size) // 2
    album_art = raw_img.resize((cover_size, cover_size), Image.LANCZOS)
    
    shadow_offset = 10
    shadow = Image.new("RGBA", (cover_size + 40, cover_size + 40), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rectangle((20, 20, cover_size + 20, cover_size + 20), fill=(0, 0, 0, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=15))
    base.paste(shadow, (cover_x - 20 + 5, cover_y - 20 + 5), shadow)

    base.paste(album_art, (cover_x, cover_y))
    draw.rectangle((cover_x, cover_y, cover_x + cover_size, cover_y + cover_size), outline=(255, 255, 255, 120), width=2)

    ui_start_x = 750
    
    clean_title = trim_to_width(title, title_font, 480)
    draw.text((ui_start_x, 180), clean_title, font=title_font, fill=(30, 30, 30, 255))
    draw.text((ui_start_x, 250), artist, font=artist_font, fill=(80, 80, 80, 255))
    draw.text((ui_start_x, 300), f"Player: {player_username}", font=player_font, fill=(120, 120, 120, 255))

    for i in range(0, 450, 10):
        v_h = random.randint(5, 30)
        draw.line((ui_start_x + i, 440 - v_h, ui_start_x + i, 440 + v_h), fill=(50, 50, 50, 180), width=3)
        
    icon_y = 510
    draw.text((ui_start_x + 60, icon_y), "❤", font=artist_font, fill=(50, 50, 50))
    draw.polygon([(ui_start_x + 150, icon_y+10), (ui_start_x + 150, icon_y+35), (ui_start_x + 130, icon_y+22)], fill=(40, 40, 40))
    draw.rectangle((ui_start_x + 200, icon_y+10, ui_start_x + 208, icon_y+35), fill=(30, 30, 30))
    draw.rectangle((ui_start_x + 215, icon_y+10, ui_start_x + 223, icon_y+35), fill=(30, 30, 30)) 
    draw.polygon([(ui_start_x + 270, icon_y+10), (ui_start_x + 270, icon_y+35), (ui_start_x + 290, icon_y+22)], fill=(40, 40, 40))
    draw.text((ui_start_x + 350, icon_y), "≡", font=artist_font, fill=(50, 50, 50))

    bar_x, bar_y, bar_w = ui_start_x, 580, 450
    draw.line((bar_x, bar_y, bar_x + bar_w, bar_y), fill=(190, 190, 190), width=5)
    draw.line((bar_x, bar_y, bar_x + 200, bar_y), fill=(40, 40, 40), width=5)
    draw.ellipse((bar_x + 195, bar_y - 6, bar_x + 207, bar_y + 6), fill=(40, 40, 40))

    draw.text((ui_start_x + 190, 615), "1:25", font=time_font, fill=(50, 50, 50))

    try:
        os.remove(thumb_path)
    except:
        pass

    base = base.convert("RGB")
    base.save(cache_path)
    return cache_path

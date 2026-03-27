import os
import re
import json
import yt_dlp
import random
import logging
import aiohttp
import asyncio
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
from AnonMusic.utils.database import is_on_off
from AnonMusic.utils.formatters import time_to_seconds

from config import BASE_API_URL, BASE_API_KEY

# Setup logging
logger = logging.getLogger(__name__)

# Cookie system configuration
COOKIES_DOWNLOADER = os.environ.get("COOKIES_DOWNLOADER", "OFF").upper() == "ON"

def cookie_txt_file():
    """Get random cookie file if cookies are enabled"""
    if not COOKIES_DOWNLOADER:
        return None
        
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir):
        return None
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        return None
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file

# Performance improvements: Connection pooling and session reuse
class DownloadSession:
    def __init__(self):
        self.session = None
        self.connector = None
        
    async def get_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=self.connector)
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector and not self.connector.closed:
            await self.connector.close()

# Global download session instance
download_session = DownloadSession()

async def download_song(link: str, use_api: bool = True):
    """Download song with improved performance"""
    video_id = link.split('v=')[-1].split('&')[0]
    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)
    
    # Check if already downloaded
    file_path = f"{download_folder}/{video_id}.mp3"
    if os.path.exists(file_path):
        logger.info(f"File already exists: {file_path}")
        return file_path
    
    # Try API if enabled
    if use_api:
        song_url = f"{BASE_API_URL}/audio?url={video_id}&api_key={BASE_API_KEY}"
        logger.info(f"Downloading audio from API: {song_url}")
        
        try:
            session = await download_session.get_session()
            async with session.get(song_url) as response:
                if response.status == 200:
                    # Use streaming with larger chunks for better performance
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(65536):  # 64KB chunks
                            if chunk:
                                f.write(chunk)
                    logger.info(f"Downloaded: {file_path}")
                    return file_path
                else:
                    logger.warning(f"API returned status {response.status}")
        except asyncio.TimeoutError:
            logger.warning("API download timeout")
        except Exception as e:
            logger.error(f"API download failed: {e}")
    
    return None

async def download_video(link: str, use_api: bool = True):
    """Download video with improved performance"""
    video_id = link.split('v=')[-1].split('&')[0]
    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)
    
    # Check if already downloaded
    file_path = f"{download_folder}/{video_id}.mp4"
    if os.path.exists(file_path):
        logger.info(f"File already exists: {file_path}")
        return file_path
    
    # Try API if enabled
    if use_api:
        video_url = f"{BASE_API_URL}/video?url={video_id}&api_key={BASE_API_KEY}"
        logger.info(f"Downloading video from API: {video_url}")
        
        try:
            session = await download_session.get_session()
            async with session.get(video_url) as response:
                if response.status == 200:
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(65536):  # 64KB chunks
                            if chunk:
                                f.write(chunk)
                    logger.info(f"Downloaded: {file_path}")
                    return file_path
                else:
                    logger.warning(f"API returned status {response.status}")
        except asyncio.TimeoutError:
            logger.warning("API download timeout")
        except Exception as e:
            logger.error(f"API download failed: {e}")
    
    return None

async def check_file_size(link):
    """Check file size using yt-dlp (only if cookies enabled)"""
    if not COOKIES_DOWNLOADER:
        return None
        
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return None
            
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f'yt-dlp error: {stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        umm = text[offset : offset + length]
        if "?si=" in umm:
            umm = umm.split("?si=")[0]
        return umm

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Try video API first (faster)
        downloaded_file = await download_video(link, use_api=True)
        if downloaded_file:
            return 1, downloaded_file
        
        # Fallback to cookies if enabled
        if COOKIES_DOWNLOADER:
            cookie_file = cookie_txt_file()
            if cookie_file:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookie_file,
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    return 1, stdout.decode().split("\n")[0]
        
        return 0, "Download failed"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        try:
            plist = await Playlist.get(link)
        except:
            return []

        videos = plist.get("videos") or []
        ids: list[str] = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        if not COOKIES_DOWNLOADER:
            return [], link
            
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return [], link
            
        ytdl_opts = {"quiet": True, "cookiefile": cookie_file}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> tuple:
        if videoid:
            link = self.base + link
        
        loop = asyncio.get_running_loop()
        
        def audio_dl():
            """Legacy audio download with cookies"""
            if not COOKIES_DOWNLOADER:
                raise Exception("Cookies downloader is disabled")
                
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found")
                
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            """Legacy video download with cookies"""
            if not COOKIES_DOWNLOADER:
                raise Exception("Cookies downloader is disabled")
                
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found")
                
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            """Legacy song video download with cookies"""
            if not COOKIES_DOWNLOADER:
                raise Exception("Cookies downloader is disabled")
                
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found")
                
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_file,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            """Legacy song audio download with cookies"""
            if not COOKIES_DOWNLOADER:
                raise Exception("Cookies downloader is disabled")
                
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found")
                
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_file,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        # Try API first for all downloads (faster)
        try:
            if songvideo or songaudio:
                # Audio download
                downloaded_file = await download_song(link, use_api=True)
                if downloaded_file:
                    return downloaded_file, True
            elif video:
                # Video download
                downloaded_file = await download_video(link, use_api=True)
                if downloaded_file:
                    return downloaded_file, True
        except Exception as e:
            logger.error(f"API download failed: {e}")
        
        # Fallback to cookies if enabled
        if COOKIES_DOWNLOADER:
            logger.info("API failed, falling back to cookies method")
            
            try:
                if songvideo or songaudio:
                    downloaded_file = await loop.run_in_executor(None, audio_dl)
                    return downloaded_file, True
                elif video:
                    cookie_file = cookie_txt_file()
                    if not cookie_file:
                        logger.error("No cookies found. Cannot download video.")
                        return None, False
                        
                    if await is_on_off(1):
                        direct = True
                        downloaded_file = await download_song(link, use_api=False)
                    else:
                        proc = await asyncio.create_subprocess_exec(
                            "yt-dlp",
                            "--cookies", cookie_file,
                            "-g",
                            "-f",
                            "best[height<=?720][width<=?1280]",
                            f"{link}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            downloaded_file = stdout.decode().split("\n")[0]
                            direct = False
                        else:
                            file_size = await check_file_size(link)
                            if not file_size:
                                logger.error("None file Size")
                                return None, False
                            total_size_mb = file_size / (1024 * 1024)
                            if total_size_mb > 250:
                                logger.error(f"File size {total_size_mb:.2f} MB exceeds the 250MB limit.")
                                return None, False
                            direct = True
                            downloaded_file = await loop.run_in_executor(None, video_dl)
                else:
                    direct = True
                    downloaded_file = await download_song(link, use_api=False)
                    
                return downloaded_file, direct
            except Exception as e:
                logger.error(f"Cookies download failed: {e}")
                return None, False
        else:
            logger.error("Cookies downloader disabled and API failed")
            return None, False

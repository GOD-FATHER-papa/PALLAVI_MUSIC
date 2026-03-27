import asyncio
import os
import random
import re
import json
import time
from pathlib import Path
from typing import Optional, Union, Tuple
from urllib.parse import quote

import aiohttp
import yt_dlp
from py_yt import Playlist, VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from config import BASE_API_URL, BASE_API_KEY
from AnonMusic.utils.database import is_on_off
from AnonMusic.utils.formatters import time_to_seconds
import logging

logger = logging.getLogger(__name__)


class FallenApi:
    def __init__(self, retries: int = 3, timeout: int = 600):
        self.api_url = BASE_API_URL.rstrip("/")
        self.api_key = BASE_API_KEY
        self.retries = retries
        self.timeout = aiohttp.ClientTimeout(total=timeout, connect=30, sock_read=timeout)
        self.session: aiohttp.ClientSession | None = None
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)
        self.download_semaphore = asyncio.Semaphore(3)

    async def get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session

    async def close_session(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _extract_youtube_id(self, link: str) -> str | None:
        pattern = re.compile(
            r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
        )
        match = pattern.search(link)
        return match.group(1) if match else link

    def _build_download_url(self, video_id: str, video: bool = False) -> str:
        """Build API URL exactly like original code"""
        endpoint = "video" if video else "audio"
        # Original format: {BASE_API_URL}/song/{video_id}?api={BASE_API_KEY}
        return f"{self.api_url}/{endpoint}/{video_id}?api={self.api_key}"

    async def download_track(
        self,
        video_id: str,
        url: str,
        video: bool = False,
        progress_callback: callable = None
    ) -> str | None:

        async with self.download_semaphore:
            download_url = self._build_download_url(video_id, video)
            
            logger.info(f"[{video_id}] Attempting API download from: {download_url}")

            for attempt in range(1, self.retries + 1):
                try:
                    session = await self.get_session()

                    async with session.get(download_url) as response:
                        logger.info(f"[{video_id}] API Response Status: {response.status}")
                        
                        if response.status != 200:
                            logger.warning(f"[{video_id}] API returned {response.status}, attempt {attempt}/{self.retries}")
                            if attempt < self.retries:
                                await asyncio.sleep(2 * attempt)
                                continue
                            return None

                        # Parse the API response
                        try:
                            data = await response.json()
                            logger.info(f"[{video_id}] API Response: {data}")
                        except Exception as e:
                            logger.error(f"[{video_id}] Failed to parse JSON: {e}")
                            return None
                        
                        status = data.get("status", "").lower()
                        logger.info(f"[{video_id}] API Status: {status}")
                        
                        if status == "done":
                            download_link = data.get("link")
                            if not download_link:
                                logger.error(f"[{video_id}] No download link in response")
                                return None
                                
                            logger.info(f"[{video_id}] Downloading from: {download_link}")
                            
                            # Download the actual file
                            async with session.get(download_link) as file_response:
                                if file_response.status != 200:
                                    logger.error(f"[{video_id}] File download failed: {file_response.status}")
                                    return None
                                    
                                filename = self._get_filename_from_response(file_response, video_id, video)
                                save_path = self.download_dir / filename
                                
                                logger.info(f"[{video_id}] Saving to: {save_path}")
                                
                                downloaded = await self._stream_download(
                                    file_response,
                                    save_path,
                                    video_id,
                                    int(file_response.headers.get('Content-Length', 0)),
                                    progress_callback
                                )
                                
                                if downloaded > 0:
                                    logger.info(f"[{video_id}] Download completed: {downloaded} bytes")
                                    return str(save_path)
                                else:
                                    logger.error(f"[{video_id}] Downloaded 0 bytes")
                                    return None
                                    
                        elif status == "downloading":
                            logger.info(f"[{video_id}] Still processing, waiting...")
                            await asyncio.sleep(4)
                            continue
                        else:
                            error_msg = data.get("error") or data.get("message") or f"Unexpected status '{status}'"
                            logger.warning(f"[{video_id}] API error: {error_msg}, attempt {attempt}/{self.retries}")
                            if attempt < self.retries:
                                await asyncio.sleep(2 * attempt)
                                continue
                            return None

                except asyncio.TimeoutError:
                    logger.error(f"[{video_id}] Timeout on attempt {attempt}/{self.retries}")
                    if attempt < self.retries:
                        await asyncio.sleep(2 * attempt)
                        continue
                    return None
                    
                except Exception as e:
                    logger.error(f"[{video_id}] Download failed on attempt {attempt}/{self.retries}: {e}")
                    if attempt == self.retries:
                        return None

                if attempt < self.retries:
                    await asyncio.sleep(2 * attempt)

            return None

    async def _stream_download(
        self,
        response: aiohttp.ClientResponse,
        save_path: Path,
        video_id: str,
        total_size: int,
        progress_callback: callable = None
    ) -> int:

        downloaded = 0

        try:
            # Import aiofiles only if needed
            try:
                import aiofiles
            except ImportError:
                # Fallback to normal file writing
                with open(save_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                await progress_callback(downloaded, total_size)
                return downloaded
                
            async with aiofiles.open(save_path, "wb") as f:
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    if chunk:
                        await f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            await progress_callback(downloaded, total_size)

        except Exception as e:
            logger.error(f"[{video_id}] Stream download error: {e}")
            if save_path.exists():
                save_path.unlink()
            return 0

        return downloaded

    def _get_filename_from_response(self, response: aiohttp.ClientResponse, video_id: str, video: bool = False) -> str:
        content_disposition = response.headers.get('Content-Disposition')

        if content_disposition:
            filename_match = re.findall(r'filename="?([^";]+)"?', content_disposition)
            if filename_match:
                filename = re.sub(r'[<>:"/\\|?*]', '', filename_match[0])
                if filename:
                    return filename

        # Default extension
        ext = "mp4" if video else "mp3"
        return f"{video_id}.{ext}"


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        
        # Initialize new API system
        self.fallen = FallenApi()
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)
        self.file_cache = {}
        
        # Log API config
        logger.info(f"API URL: {BASE_API_URL}")
        logger.info(f"API Key: {BASE_API_KEY[:10]}..." if BASE_API_KEY else "API Key not set")

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
        
        # Try new API first
        video_id = link.split('v=')[-1].split('&')[0]
        try:
            logger.info(f"Attempting video download via API for: {video_id}")
            downloaded_file = await self.fallen.download_track(video_id, link, video=True)
            if downloaded_file:
                logger.info(f"Video downloaded via API: {downloaded_file}")
                return 1, downloaded_file
            else:
                logger.warning(f"API returned no file for video: {video_id}")
        except Exception as e:
            logger.error(f"Video API failed: {e}")
        
        # Fallback to cookies method
        logger.info(f"Falling back to cookies for video: {video_id}")
        cookie_file = self.get_cookie_file()
        if not cookie_file:
            logger.error("No cookies found for video fallback")
            return 0, "No cookies found. Cannot download video."
            
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
        else:
            return 0, stderr.decode()

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
        
        cookie_file = self.get_cookie_file()
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
    ) -> Tuple[Optional[str], bool]:
        
        if videoid:
            link = self.base + link
        
        video_id = link.split('v=')[-1].split('&')[0]
        
        # ALWAYS try API first
        logger.info(f"Download requested: video_id={video_id}, video={video}, songaudio={songaudio}, songvideo={songvideo}")
        
        try:
            if songvideo or songaudio or not video:
                # Audio download
                logger.info(f"Attempting audio download via API for: {video_id}")
                downloaded_file = await self.fallen.download_track(video_id, link, video=False)
                if downloaded_file:
                    logger.info(f"Audio downloaded via API: {downloaded_file}")
                    return downloaded_file, True
                else:
                    logger.warning(f"API returned no file for audio: {video_id}")
            elif video:
                # Video download
                logger.info(f"Attempting video download via API for: {video_id}")
                downloaded_file = await self.fallen.download_track(video_id, link, video=True)
                if downloaded_file:
                    logger.info(f"Video downloaded via API: {downloaded_file}")
                    return downloaded_file, True
                else:
                    logger.warning(f"API returned no file for video: {video_id}")
        except Exception as e:
            logger.error(f"API download failed: {e}", exc_info=True)
        
        # If API fails, try cookies method
        logger.info(f"API failed, falling back to cookies method for: {video_id}")
        return await self._download_fallback(link, video, songaudio, songvideo, format_id, title)

    async def _download_fallback(self, link, video, songaudio, songvideo, format_id, title):
        """Fallback to yt-dlp with cookies"""
        cookie_file = self.get_cookie_file()
        if not cookie_file:
            logger.error("No cookies found for fallback download")
            return None, False
            
        loop = asyncio.get_running_loop()
        
        def audio_dl():
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

        if songvideo or songaudio:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True
        elif video:
            if await is_on_off(1):
                direct = True
                downloaded_file = await loop.run_in_executor(None, audio_dl)
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
                    file_size = await self.check_file_size(link)
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
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            
        return downloaded_file, direct

    def get_cookie_file(self):
        cookie_dir = f"{os.getcwd()}/cookies"
        if not os.path.exists(cookie_dir):
            return None
        cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
        if not cookies_files:
            return None
        cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
        return cookie_file

    async def check_file_size(self, link: str):
        async def get_format_info(link):
            cookie_file = self.get_cookie_file()
            if not cookie_file:
                logger.error("No cookies found. Cannot check file size.")
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
                logger.error(f'Error:\n{stderr.decode()}')
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
            logger.error("No formats found.")
            return None
        
        total_size = parse_size(formats)
        return total_size

    async def close(self):
        """Clean up resources"""
        await self.fallen.close_session()


# Create global instance
youtube_api = YouTubeAPI()

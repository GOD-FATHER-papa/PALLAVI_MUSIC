from .logging import LOGGER

from AnonMusic.core.bot import Anony
from AnonMusic.core.userbot import Userbot
from AnonMusic.utils.downloader import Downloader

from AnonMusic.core.dir import dirr
from AnonMusic.core.git import git
from AnonMusic.misc import dbb, heroku

from .platforms import (
    AppleAPI,
    CarbonAPI,
    SoundAPI,
    SpotifyAPI,
    RessoAPI,
    TeleAPI,
    YouTubeAPI,
)

dirr()
git()
dbb()
heroku()

app = Anony()
userbot = Userbot()
downloader = Downloader()

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

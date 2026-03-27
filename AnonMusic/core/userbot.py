from pyrogram import Client
import config
from ..logging import LOGGER

assistants = []
assistantids = []


class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="AnonXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            name="AnonXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            name="AnonXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            name="AnonXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            name="AnonXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    async def start(self):
        LOGGER(__name__).info(f"Starting Assistants...")
        
        assistants_config = [
            (self.one, config.STRING1, 1),
            (self.two, config.STRING2, 2),
            (self.three, config.STRING3, 3),
            (self.four, config.STRING4, 4),
            (self.five, config.STRING5, 5),
        ]
        
        for client, string, num in assistants_config:
            if string:
                await client.start()
                try:
                    await client.join_chat("VibeBots")
                    await client.join_chat("VibeBotsSupport")
                except:
                    pass
                
                assistants.append(num)
                
                try:
                    await client.send_message(config.LOG_GROUP_ID, "Assistant Started")
                except:
                    LOGGER(__name__).error(
                        f"Assistant Account {num} has failed to access the log Group. Make sure that you have added your assistant to your log group and promoted as admin!"
                    )
                    exit()
                
                client.id = client.me.id
                client.name = client.me.mention
                client.username = client.me.username
                assistantids.append(client.id)
                
                LOGGER(__name__).info(f"Assistant {num} Started as {client.name}")

    async def stop(self):
        LOGGER(__name__).info(f"Stopping Assistants...")
        for client in [self.one, self.two, self.three, self.four, self.five]:
            try:
                await client.stop()
            except:
                pass

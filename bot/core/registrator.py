from pyrogram import Client
from bot.config import settings
from bot.utils import logger

async def register_sessions() -> None:
    API_ID = settings.API_ID
    API_HASH = settings.API_HASH

    if not API_ID or not API_HASH:
        raise ValueError("API_ID and API_HASH not found in the .env file.")

    while True:
        session_name = input('\nEnter the session name (or press Enter to exit): ').strip()
        if not session_name:
            break

        session = Client(
            name=session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir="sessions/"
        )

        async with session:
            user_data = await session.get_me()
            logger.success(f'Session - {session_name} | Username @{user_data.username} added successfully')

        next_session = input("\nAdd another session? (y/n): ").strip().lower()
        if next_session != 'y':
            break

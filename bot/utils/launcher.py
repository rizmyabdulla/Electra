import os
import glob
import asyncio
import argparse
from itertools import cycle

from pyrogram import Client
from better_proxy import Proxy

from bot.config import settings
from bot.utils import logger
from bot.core.tapper import run_query_tapper, run_query_tapper1, run_tapper, run_tapper1
from bot.core.registrator import register_sessions

start_text = """
Select an action:

    1. Run clicker (Session)
    2. Create session
    3. Run clicker (Query)
"""

async def process(action: int = None) -> None:
    logger.info(f"Detected {len(get_session_names())} sessions | {len(get_proxies())} proxies")
    if action is None:
        print(start_text)
        while True:
            action_input = input("> Select an action: ").strip()
            if action_input.isdigit() and action_input in ["1", "2", "3"]:
                action = int(action_input)
                break
            logger.warning("Action must be 1, 2, or 3")
    
    await run_action(action)


def get_session_names() -> list[str]:
    session_names = sorted(glob.glob("sessions/*.session"))
    return [os.path.splitext(os.path.basename(file))[0] for file in session_names]

def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open("bot/config/proxies.txt", encoding="utf-8-sig") as file:
            return [Proxy.from_str(row.strip()).as_url for row in file]
    return []

async def get_tg_clients() -> list[Client]:
    global tg_clients

    session_names = get_session_names()

    if not session_names:
        raise FileNotFoundError("Not found session files")

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError("API_ID and API_HASH not found in the .env file.")

    tg_clients = [
        Client(
            name=session_name,
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            workdir="sessions/",
            plugins=dict(root="bot/plugins"),
        )
        for session_name in session_names
    ]

    return tg_clients

async def run_action(action: int) -> None:
    if action == 2:
        await register_sessions()
    elif action == 1:
        await execute_clicker_action()
    elif action == 3:
        await execute_query_action()

async def execute_clicker_action():
    tg_clients = await get_tg_clients()
    multi_thread = input("> Run bot with multi-thread? (y/n): ").lower() == 'y'

    if multi_thread:
        await run_tasks(tg_clients)
    else:
        proxies = get_proxies()
        await run_tapper1(tg_clients, proxies=proxies)

async def execute_query_action():
    with open("data.txt", "r") as f:
        query_ids = [line.strip() for line in f.readlines()]
    multi_thread = input("> Run bot with multi-thread? (y/n): ").lower() == 'y'

    if multi_thread:
        await run_tasks_query(query_ids)
    else:
        proxies = get_proxies()
        await run_query_tapper1(query_ids, proxies=proxies)

async def run_tasks_query(query_ids: list[str]):
    proxies = get_proxies()
    proxies_cycle = cycle(proxies) if proxies else None
    tasks = [
        asyncio.create_task(
            run_query_tapper(query, proxy=next(proxies_cycle) if proxies_cycle else None, name=f"Account{idx}")
        )
        for idx, query in enumerate(query_ids)
    ]
    await asyncio.gather(*tasks)

async def run_tasks(tg_clients: list[Client]):
    proxies = get_proxies()
    proxies_cycle = cycle(proxies) if proxies else None
    tasks = [
        asyncio.create_task(
            run_tapper(tg_client=tg_client, proxy=next(proxies_cycle) if proxies_cycle else None)
        )
        for tg_client in tg_clients
    ]
    await asyncio.gather(*tasks)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")
    args = parser.parse_args()

    action = args.action
    if not action:
        print(start_text)
        action = int(input("> Select an action: ").strip())

    await run_action(action)

if __name__ == "__main__":
    asyncio.run(main())

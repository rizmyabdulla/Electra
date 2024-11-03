import asyncio
import random
import sys
import traceback
from itertools import cycle
from time import time

import hmac
import hashlib
import aiohttp
from datetime import datetime, timedelta

import requests
import pytz
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from bot.core.agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint
import math

from pyrogram.raw import functions
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView
from urllib.parse import unquote


ENDPOINT = "https://europe-west1-mesocricetus-raddei.cloudfunctions.net/api"
store_sleeps = []
class Tapper:
    def __init__(self, query: str, session_name: str, multi_thread, tg_client: Client):
        self.tg_client = tg_client
        self.session_name = session_name
        self.query = query
        self.user_id = ''
        self.auth_token = ""
        self.ref_id = "krkbtSox"
        self.multi_thread = multi_thread

    async def get_tg_web_data(self, proxy: str | None) -> str:
        try:
            ref_param = settings.REF_LINK.split("?")[1] if settings.REF_LINK else "startapp=krkbtSox"
            self.ref_id = settings.REF_LINK.split('=')[1] if settings.REF_LINK else "krkbtSox"

            proxy_dict = None
            if proxy:
                proxy = Proxy.from_str(proxy)
                proxy_dict = {
                    'scheme': proxy.protocol,
                    'hostname': proxy.host,
                    'port': proxy.port,
                    'username': proxy.login,
                    'password': proxy.password
                }

            self.tg_client.proxy = proxy_dict

            if not await self.tg_client.connect():
                try:
                    async for message in self.tg_client.get_chat_history('ElectraAppBot', limit=50):
                        if message.text and message.text.startswith('/start'):
                            break
                    else:
                        peer = await self.tg_client.resolve_peer('ElectraAppBot')
                        await self.tg_client.invoke(
                            functions.messages.StartBot(
                                bot=peer,
                                peer=peer,
                                start_param="dex?" + ref_param,
                                random_id=randint(1, 9999999),
                            )
                        )
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered) as e:
                    raise InvalidSession(self.session_name) from e

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('ElectraAppBot')
                    break
                except FloodWait as fl:
                    logger.warning(f"{self.session_name} | <yellow>FloodWait {fl.value}s. Retrying...</yellow>")
                    await asyncio.sleep(fl.value + 3)

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=peer,
                bot=peer,
                platform='android',
                from_bot_menu=True,
                url="https://tg-app-embed.electra.trade",
                start_param=ref_param
            ))
            auth_url = web_view.url

            tg_web_data = unquote(auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            
            logger.error(f"{self.session_name} | <red>Unknown error during Authorization:</red> {error}")
            await asyncio.sleep(3)


    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy):
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | <green>Proxy IP: {ip}</green>")
            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | <red>Error:</red> {error}")

            return False

    async def get_user_info(self, session: requests.Session):
        try:
            res = session.get(f"{ENDPOINT}/userData", headers=headers)
            if res.status_code == 200:
                user = res.json()
                return user
            else:
                logger.warning(f"{self.session_name} | <yellow>Get user info failed: {res.status_code}</yellow>")
                return None
        except:
            return None

    async def get_settings(self, session: requests.Session):
        try:
            res = session.get(f"{ENDPOINT}/settings", headers=headers)
            if res.status_code == 200:
                response = res.json()
                return response
            else:
                logger.warning(f"{self.session_name} | <yellow>Get Task List failed: {res.status_code}</yellow>")
                return None
        except:
            logger.error(f"{self.session_name} | <red>Error:</red> {traceback.format_exc()}")
            return None


    async def update_streak(self, session: requests.Session):

        try:
            res = session.post(f"{ENDPOINT}/updateStreak", headers=headers)
            if res.status_code == 200:
                streak_res = res.json()
                logger.success(f"{self.session_name} | <green>Update Streak successfully! Reward: {streak_res['points']} | Streak: {len(streak_res['daily_streak'])}</green>")
            elif res.status_code == 500:
                logger.warning(f"{self.session_name} | <yellow>Already claimed daily streak!</yellow>")
            else:
                logger.warning(f"{self.session_name} | <yellow>Update Streak failed: {res.status_code}</yellow>")
        except:
            logger.error(f"{self.session_name} | <red>Error:</red> {traceback.format_exc()}")


    async def do_tasks(self, session: requests.Session):
        try:
            setting = await self.get_settings(session)
            user_info = await self.get_user_info(session)
            task_list = setting.get('TASK_LIST', [])
            user_tasks = user_info['user'].get('tasks', {})

            if not task_list:
                logger.warning(f"{self.session_name} | <yellow>No tasks found or failed to retrieve tasks.</yellow>")
                return

            for task in task_list:
                task_id = task['id']
                task['status'] = user_tasks.get(task_id, {}).get('status', 'todo')

            mega_tasks, other_tasks = self.split_tasks(task_list)

            await self.process_tasks(mega_tasks, session, is_mega=True)
            await self.verify_and_claim_mega_tasks(session)

            await self.process_tasks(other_tasks, session, is_mega=False)

            completed_tasks = [task for task in task_list if task['status'] == "done"]
            if len(completed_tasks) == len(task_list):
                logger.info(f"{self.session_name} | Tasks Completed: {len(completed_tasks)} / {len(task_list)}.")
                logger.info(f"{self.session_name} | <green>All tasks are completed!</green>")
            else:
                remaining_tasks = len(task_list) - len(completed_tasks)
                logger.info(f"{self.session_name} | Tasks Completed: {len(completed_tasks)} / {len(task_list)}.")
                logger.info(f"{self.session_name} | <yellow>{remaining_tasks} tasks still pending.</yellow>")

        except Exception as e:
            logger.error(f"{self.session_name} | <red>Error:</red> {traceback.format_exc()}")


    async def process_tasks(self, tasks, session: requests.Session, is_mega: bool = False):
        for task in tasks:
            task_id = task['id']
            data = {"task_id": task_id, "status": "done"}
            res = session.post(f"{ENDPOINT}/taskProcess", headers=headers, json=data)
            task_type = "Mega Task" if is_mega else "Task"
            if res.status_code == 200:
                logger.success(f"{self.session_name} | {task_type} '{task['title']}' completed! <yellow>reward: {task['points']} points</yellow>")
            else:
                premium_msg = " | Hint: This task is for premium users only" if task.get('is_premium') else ""
                logger.warning(f"{self.session_name} | <yellow>Failed to complete {task_type} '{task['title']}': {res.status_code}{premium_msg}</yellow>")


    async def verify_and_claim_mega_tasks(self, session: requests.Session):
        try:
            res = session.get(f"{ENDPOINT}/verifyMegaTasks", headers=headers)
            if res.status_code == 200:
                response = res.json()
                if response['mega_tasks']['completed'] and not response['mega_tasks']['claimed']:
                    await self.claim_mega_reward(session)
                elif response['mega_tasks']['completed']:
                    logger.warning(f"{self.session_name} | <yellow>Mega Tasks reward already claimed!</yellow>")
            else:
                logger.warning(f"{self.session_name} | <yellow>Mega Tasks verification failed: {res.status_code}</yellow>")
        except Exception as e:
            logger.error(f"{self.session_name} | <red>Error:</red> {traceback.format_exc()}")


    async def claim_mega_reward(self, session: requests.Session):
        res = session.get(f"{ENDPOINT}/claimMegaTaskReward", headers=headers)
        if res.status_code == 200:
            response = res.json()
            logger.success(f"{self.session_name} | Mega Tasks successfully claimed! <yellow>reward: {response['points']} points</yellow>")
        else:
            logger.warning(f"{self.session_name} | <yellow>Mega Tasks reward claim failed: {res.status_code} | {res.json()}</yellow>")


    def split_tasks(self, task_list):
        mega_tasks = [task for task in task_list if task['type'] == "mega" and task['status'] in ["todo", "verification_in_progress"]]
        other_tasks = [task for task in task_list if task['type'] != "mega" and task['status'] in ["todo", "verification_in_progress"]]
        return mega_tasks, other_tasks

    async def farming(self, guess_type, session: requests.Session):

        if guess_type == "random":
            guess_type = "up" if random.choice([True, False]) else "down"

        user_response = await self.get_user_info(session)
        user = user_response['user']

        setting = await self.get_settings(session)
        farm_hours = setting['FARM_HOURS']

        try:
            if user.get('farming_started', 0) != 0:
                tt = user['farming_started'] / 1000
                start_time = datetime.fromtimestamp(tt)
                current_time = datetime.now()
                time_diff = current_time - start_time

                farming_duration = timedelta(hours=farm_hours)

                if time_diff >= farming_duration:
                    try:
                        res = session.get(f"{ENDPOINT}/guessBtcPrice", headers=headers)
                        if res.status_code == 200:
                            response = res.json()
                            if user["guess"]["type"] == "up" and response["diff"] > 0 or user["guess"]["type"] == "down" and response["diff"] < 0:
                                logger.success(f"{self.session_name} | Farming ended successfully. <green> BTC price guessed CORRECT! </green> | BTC price went {'<green>UP</green>' if response['diff'] > 0 else '<red>DOWN</red>'}!")
                            elif user["guess"]["type"] == "up" and response["diff"] < 0 or user["guess"]["type"] == "down" and response["diff"] > 0:
                                logger.success(f"{self.session_name} | Farming ended successfully. <red> BTC price guessed wrong! :( </red> | BTC price went {'<green>UP</green>' if response['diff'] > 0 else '<red>DOWN</red>'}!")
                            else:
                                logger.warning(f"{self.session_name} | <yellow>Failed to guess BTC price: {res.status_code}</yellow>")
                            
                            reset_data = {}
                            res1 = session.post(f"{ENDPOINT}/resetFarming", headers=headers, json=reset_data)
                            if res1.status_code == 200:
                                logger.success(f"{self.session_name} | Farming reset successfully.")
                                # guess type "up" or "down"
                                await self.start_farming(guess_type, session)
                            else:
                                logger.warning(f"{self.session_name} | Failed to reset farming: {res1.status_code} | {res1.json()}")
                        else:
                            logger.warning(f"{self.session_name} | Reset failed: {res.status_code}")
                    except Exception as e:
                        logger.error(f"{self.session_name} | <red>Reset Error:</red> {traceback.format_exc()}")


                else:
                    time_left = farming_duration - time_diff
                    hours_left, remainder = divmod(time_left.total_seconds(), 3600)
                    minutes_left = remainder // 60
                    logger.warning(f"{self.session_name} | Farming already started. Time left to claim: {int(hours_left)}h {int(minutes_left)}m")

            else:
                # guess type "up" or "down"
                await self.start_farming(guess_type, session)

        except Exception as main_error:
            logger.error(f"{self.session_name} | <red>General Error:</red> {traceback.format_exc()}")


    async def start_farming(self,guess_type, session: requests.Session):
        start_data = {"guess": {"type": guess_type}}
        try:
            res = session.post(f"{ENDPOINT}/startFarming", headers=headers, json=start_data)
            if res.status_code == 200:
                logger.success(f"{self.session_name} | Farming started successfully. Guess: BTC GOES {'<green>UP</green>' if guess_type == 'up' else '<red>DOWN</red>'}!")
            else:
                logger.warning(f"{self.session_name} | Failed to start farming: {res.status_code}")
        except Exception as e:
            logger.error(f"{self.session_name} | <red>Start Error:</red> {traceback.format_exc()}")


    async def upgrade_level(self, session: requests.Session):
        user_response = await self.get_user_info(session)
        setting = await self.get_settings(session)

        upgrade_level_list = setting['UPGRADE_LEVEL_LIST']
        user = user_response['user']
        
        rates_map = {level_info["rate"]: level for level, level_info in enumerate(upgrade_level_list)}

        current_rate = user['upgrade_level']
        
        if current_rate == 1:
            current_level = -1
        elif current_rate in rates_map:
            current_level = rates_map[current_rate]
        else:
            logger.error(f"{self.session_name} | Invalid upgrade level rate: {current_rate}")
            return

        next_level = current_level + 1
        if next_level < len(upgrade_level_list):
            upgrade_price = upgrade_level_list[next_level]['price']
            next_rate = upgrade_level_list[next_level]['rate']
            logger.info(f"{self.session_name} | Current Upgrade Rate: x{current_rate} | Next Upgrade Rate: x{next_rate} | Upgrade Price: {upgrade_price}")

            if user['points'] >= upgrade_price:
                data = {
                    "upgradeLevel": next_rate,
                    "price": upgrade_price
                }
                try:
                    res = session.post(f"{ENDPOINT}/updateUpgradeLevel", headers=headers, json=data) 
                    if res.status_code == 200:
                        logger.success(f"{self.session_name} | Level upgraded successfully. <green> Rate: x{next_rate} | Upgrade Price: {upgrade_price} </green>")
                    else:
                        logger.warning(f"{self.session_name} | Failed to upgrade level: {res.status_code}")
                except Exception as e:
                    logger.error(f"{self.session_name} | <red>Upgrade Error:</red> {traceback.format_exc()}")

            else:
                logger.warning(f"{self.session_name} | Not enough points to upgrade.")
        else:
            logger.info(f"{self.session_name} | Max upgrade level reached.")

    async def calculate_next_farming_time(self, session: requests.Session):
        user_info = await self.get_user_info(session)
        setting = await self.get_settings(session)
        farm_hours = setting.get('FARM_HOURS', 6)

        if user_info['user'].get('farming_started') != 0:
            start_timestamp = user_info['user']['farming_started'] / 1000
            start_time = datetime.fromtimestamp(start_timestamp)
            next_farming_time = start_time + timedelta(hours=farm_hours)
        else:
            next_farming_time = datetime.now() + timedelta(hours=farm_hours)

        return next_farming_time


    async def run(self, proxy: str | None) -> None:
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        headers["User-Agent"] = generate_random_user_agent(device_type='windows', browser_type='chrome')
        
        async with CloudflareScraper(headers=headers, connector=proxy_conn) as http_client:
            session = requests.Session()

            if proxy:
                if await self.check_proxy(http_client=http_client, proxy=proxy):
                    session.proxies.update({proxy.split(':')[0]: proxy})
                    logger.info(f"{self.session_name} | Bound to proxy IP: {proxy}")
                else:
                    logger.error(f"{self.session_name} | Proxy check failed. Exiting run.")
                    return False

            while True:
                try:
                    if self.query is not None:
                        tg_web_data = self.query
                    elif self.tg_client is not None:
                        tg_web_data = await self.get_tg_web_data(proxy)

                    headers['X-telegram-init-data'] = tg_web_data
                    self.auth_token = tg_web_data

                    user_info = await self.get_user_info(session)
                    if not user_info:
                        logger.error(f"{self.session_name} | Failed to fetch user information. Exiting run.")
                        break

                    user = user_info['user']
                    print("\n")
                    logger.info(f"{self.session_name} | Username: <light-yellow>{user['username']}</light-yellow> | Points: <light-yellow>{user['points']}</light-yellow>")

                    await asyncio.gather(
                        self.update_streak(session),
                        self.do_tasks(session),
                        self.farming(guess_type=settings.BTC_PRICE_GUESS, session=session),
                        self.upgrade_level(session)
                    )

                    next_farming_time = await self.calculate_next_farming_time(session)

                    time_to_next_farming = (next_farming_time - datetime.now()).total_seconds()
                    sleep_duration = max(0, time_to_next_farming - 5)

                    logger.info(f"{self.session_name} | <light-yellow>Sleeping until next farming time: {int(sleep_duration / 60)} minutes</light-yellow>")
                    store_sleeps.append(sleep_duration)
                    await asyncio.sleep(sleep_duration)

                except Exception as error:
                    logger.error(f"{self.session_name} | <red>Error:</red> {error}")

                    break

                if self.multi_thread:
                    logger.info(f"{self.session_name} | Running in multi-thread mode. Waiting until farming time.")
                    continue
                else:
                    session.close()
                    break

async def run_query_tapper(query: str, name: str, proxy: str | None):
    try:
        sleep_ = randint(1, 15)
        logger.info(f"{name} | Start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(query=query, tg_client=None, session_name=name, multi_thread=True).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"Invalid Query: {query}")

async def run_query_tapper1(queries: list[str], proxies):
    proxies_cycle = cycle(proxies) if proxies else None
    name = "Account"

    while True:
        i = 0
        for query in queries:
            try:
                await run_query_tapper(query=query,tg_client=None, name=f"{name} {i}", proxy=next(proxies_cycle) if proxies_cycle else None)
            except InvalidSession:
                logger.error(f"Invalid Query: {query}")

            sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
            logger.info(f"{name} {i} | Sleep {sleep_}s...")
            await asyncio.sleep(sleep_)

            i += 1 
        sleep_ = min(store_sleeps)
        logger.info(f"<red>Sleep {int(sleep_ / 60)} minutes...</red>")
        await asyncio.sleep(sleep_)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        sleep_ = randint(1, 15)
        logger.info(f"{tg_client.name} | start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(query=None, tg_client=tg_client,session_name=tg_client.name, multi_thread=True).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")

async def run_tapper1(tg_clients: list[Client], proxies):
    proxies_cycle = cycle(proxies) if proxies else None
    while True:
        for tg_client in tg_clients:
            try:
                await Tapper(query=None, tg_client=tg_client ,session_name=tg_client.name, multi_thread=False).run(next(proxies_cycle) if proxies_cycle else None)
            except InvalidSession:
                logger.error(f"{tg_client.name} | Invalid Session")

            sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
            logger.info(f"Sleep {sleep_}s...")
            await asyncio.sleep(sleep_)

        sleep_ = min(store_sleeps)
        logger.info(f"<red>Sleep {int(sleep_ / 60)} minutes...</red>")
        await asyncio.sleep(sleep_)
import requests
import time
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HEADERS = {
    'X-API-KEY': 'yourtoken'
}
FETCH_TRADES_URL = "https://servapi.dbotx.com/account/follow_trades"
EDIT_FOLLOW_ORDER_URL = "https://api-bot-v1.dbotx.com/automation/follow_order"
ASSET_API_URL = "https://servapi.dbotx.com/account/wallet/assets?page={page}&size=100&walletAddress={walletAddress}&chain=solana&sortBy=timestamp&minValueUsd"
FOLLOW_ORDERS_API_URL = "https://api-bot-v1.dbotx.com/automation/follow_orders"
wallets_URL = "https://api-bot-v1.dbotx.com/account/wallets"
SWAP_URL = "https://api-bot-v1.dbotx.com/automation/swap_order"

sumLoss = -2
fast_pairs_count = 2
holdtimes = 5*60

# Telegram Bot details
BOT_TOKEN = "yourToken"
CHAT_ID = 7096464619

Pardon = ['mhrthc5e0334zt','mhrthcgr07qqnv']

def request_data(url, params=None, max_retries=3, retry_delay=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            time.sleep(retry_delay)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return {}
    logger.error(f"请求失败，已达到最大重试次数: {url}")
    return {}

def send_message_via_telegram(message):
    """发送消息到Telegram群组"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"  # 你可以选择'HTML'或'Markdown'
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        print("Message sent successfully")
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as err:
        print(f"An error occurred: {err}")

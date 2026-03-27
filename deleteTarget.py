# -*- coding: utf-8 -*-

import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    'X-API-KEY': 'yourtoken'
}
API_URL = "https://servapi.dbotx.com/account/follow_trades"
EDIT_FOLLOW_ORDER_URL = "https://api-bot-v1.dbotx.com/automation/follow_order"
ASSET_API_URL = "https://servapi.dbotx.com/account/wallet/assets?page={page}&size=100&walletAddress={walletAddress}&chain=solana&sortBy=timestamp&minValueUsd"
FOLLOW_ORDERS_API_URL = "https://api-bot-v1.dbotx.com/automation/follow_orders"

# Telegram Bot details
BOT_TOKEN = "yourToken"
CHAT_ID = 7096464619

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

#获取指定wallet的全部资产信息
def fetch_wallet_assets(wallet_address):
    """递增 page 参数，获取指定钱包的所有资产数据"""
    all_assets = []  # 存储所有资产
    page = 0  # 初始化页面编号

    while True:
        url = ASSET_API_URL.format(page=page,walletAddress=wallet_address)
        
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()  # 检查请求是否成功
            data = response.json()  # 返回 JSON 数据
            
            # 检查是否有资产数据
            if data and "res" in data and data["res"]:
                all_assets.extend(data["res"])  # 添加当前页的资产数据
                page += 1  # 递增页面编号
                time.sleep(1)
            else:
                break  # 如果没有资产，退出循环

        except requests.RequestException as e:
            print(f"请求失败: {e}")
            time.sleep(2)

    return all_assets  # 返回所有资产数据

#将资产信息整理为字典格式：{token:pnl}
def extract_token_info(assets):
    token_info = {}
    time_limit = datetime.now() - timedelta(hours=24)
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        token = asset.get("token")
        pnl = asset.get("pnl", 0)
        if token:
            token_info[token] = pnl
    return token_info

#获取每个configId下的每个copy_wallet在24h内购买的token列表、及其对应的configName、myWallet
def fetch_trades():
    '''
     copy_wallet在24h内的交易token信息：
     [{
            "configId": config_id,
            "configName": details['configName'],
            "myWallet": details['myWallet'],
            "followWallet": wallet,
            "tokens": list(details['tokens'])
           },...]
    '''
    trades_info = defaultdict(lambda: defaultdict(lambda: {'tokens': set(), 'configName': '', 'myWallet': ''}))
    params = {"chain": "", "page": 0, "size": 100, "type": "buy"}
    time_limit = datetime.now() - timedelta(hours=24)

    while True:
        data = request_data(API_URL, params=params)
        if not data or not isinstance(data.get('res'), list):
            break

        recent_trades = [
            trade for trade in data['res']
            if isinstance(trade, dict) and trade.get('createAt') and
            datetime.fromtimestamp(trade['createAt'] / 1000) >= time_limit
        ]

        if not recent_trades:
            break

        filter_and_aggregate_trades(recent_trades, trades_info)
        params['page'] += 1
        time.sleep(1)

    return [
        {
            "configId": config_id,
            "configName": details['configName'],
            "myWallet": details['myWallet'],
            "followWallet": wallet,
            "tokens": list(details['tokens'])
        }
        for config_id, wallets in trades_info.items()
        for wallet, details in wallets.items()
    ]

def filter_and_aggregate_trades(trade_records, trades_info):
    for trade in trade_records:
        if not isinstance(trade, dict) or trade.get('state') != 'done':
            continue
        follow_info = trade.get("follow", {})
        target_wallet = follow_info.get("wallet")
        config_id = trade.get("configId")
        token = trade.get("receive", {}).get("info", {}).get("contract")
        if config_id and target_wallet and token:
            trades_info[config_id][target_wallet]['tokens'].add(token)
            trades_info[config_id][target_wallet]['configName'] = trade.get("configName", "")
            trades_info[config_id][target_wallet]['myWallet'] = trade.get("wallet", "")

#根据更新类型，更新指定id的任务
def update_targetId(targetId, config_id, update_type='del'):
    """
    从指定配置中添加或删除 targetId。
    
    参数:
        targetId (str): 要添加或删除的目标 ID。
        config_id (str): 要操作的配置 ID。
        update_type (str): 'del' 或 'add'，表示删除或添加操作。
    
    返回:
        str: 成功消息或错误信息。
        int: 0 表示操作失败。
    """
    params = {
        'page': 0,
        'size': 20
    }
    if config_id in ['mhrthc5e0334zt','mhrthcgr07qqnv']:
        logging.info(f"免死 {config_id}。")
        return 0
        
    while True:
        try:
            # 发送 GET 请求
            response = requests.get(
                'https://api-bot-v1.dbotx.com/automation/follow_orders',
                headers=HEADERS,
                params=params,
                timeout=10  # 设置超时
            )
            response.raise_for_status()  # 抛出 HTTP 错误
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"GET 请求失败: {e}")
            return 0
        except ValueError as e:
            logging.error(f"JSON 解析失败: {e}")
            return 0

        # 获取响应中的数据列表
        tmp = data.get('res', [])
        if not isinstance(tmp, list):
            logging.error("API 返回的 'res' 字段不是列表")
            return 0

        if not tmp:
            # 没有更多数据，退出循环
            logging.info("没有更多数据，退出循环")
            break

        for a in tmp:
            if not isinstance(a, dict):
                logging.warning("发现非字典条目，跳过")
                continue

            current_id = a.get('id')
            if current_id == config_id:
                # 找到目标配置
                try:
                    # 获取 targetIds 列表
                    target_ids = a.get('targetIds', [])
                    if not isinstance(target_ids, list):
                        logging.error(f"配置 {config_id} 的 targetIds 不是列表")
                        return 0

                    # 判断是否需要修改
                    modified = False
                    if update_type == 'del':
                        if targetId in target_ids:
                            target_ids.remove(targetId)
                            modified = True
                        else:
                            name = a.get('name', '未知名称')
                            message = f"Target ID {targetId} 不存在于 {name}，无需删除"
                            logging.info(message)
                            return message
                    elif update_type == 'add':
                        if targetId not in target_ids:
                            target_ids.append(targetId)
                            modified = True
                        else:
                            name = a.get('name', '未知名称')
                            message = f"Target ID {targetId} 已存在于 {name}，无需添加"
                            logging.info(message)
                            return message
                    else:
                        logging.error(f"未知的 update_type: {update_type}")
                        return 0

                    # 如果需要修改，发送 POST 请求
                    if modified:
                        try:
                            post_response = requests.post(
                                EDIT_FOLLOW_ORDER_URL,
                                headers=HEADERS,
                                json=a,
                                timeout=10
                            )
                            post_response.raise_for_status()
                            post_data = post_response.json()
                        except requests.exceptions.RequestException as e:
                            logging.error(f"POST 请求失败: {e}")
                            return 0
                        except ValueError as e:
                            logging.error(f"POST 响应 JSON 解析失败: {e}")
                            return 0

                        if post_data.get('err'):
                            error_msg = post_data.get('msg', '未知错误')
                            logging.error(f"服务器返回错误: {error_msg}")
                            return 0

                        name = a.get('name', '未知名称')
                        if update_type == 'del':
                            message = f"成功从 {name} 删除 {targetId}！"
                        else:
                            message = f"成功向 {name} 添加 {targetId}！"
                        logging.info(message)
                        return message

                    # 如果未修改，已返回成功信息
                    return 0

                except Exception as inner_e:
                    logging.error(f"处理配置 {config_id} 时发生异常: {inner_e}")
                    return 0

        # 继续下一页
        params['page'] += 1
        time.sleep(1)

    # 所有页面遍历完成，未找到 config_id
    logging.info(f"未找到配置 ID {config_id}。")
    return 0

#获取指定wallet配置段只跟卖的任务id
def get_disabled_buy_task_ids(wallet_address, configName, timeout=10):
    """
    根据指定的 wallet address，返回 buySettings.enabled 为 False 的任务的 id 列表。

    """
    params = {
        'page': 0,
        'size': 20
    }
    try:
        while True:
            response = requests.get(
                'https://api-bot-v1.dbotx.com/automation/follow_orders',
                headers=HEADERS,
                params=params,
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            res = data.get('res', [])
            if not isinstance(res, list):
                logger.error("API 返回数据结构异常，'res' 不是列表。")
                break

            if not res:
                break  # 没有更多数据

            for item in res:
                if not isinstance(item, dict):
                    continue  # 跳过无效数据

                wa = item.get('walletAddress')
                buy_settings = item.get('buySettings', {})

                if not isinstance(buy_settings, dict):
                    continue  # buySettings 不是字典，跳过

                enabled = buy_settings.get('enabled')

                if wa == wallet_address and enabled is False:
                    return item.get('id')


            params['page'] += 1
            time.sleep(1)

    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {e}")
        return 0
    except ValueError as e:
        logger.error(f"JSON 解析失败: {e}")
        return 0
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return 0
        
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


def main():
    data_list = fetch_trades()
    if not data_list:
        logger.info("未获取到交易数据，程序结束")
        return
    grouped_data = defaultdict(list)
    for item in data_list:
        grouped_data[item['myWallet']].append(item)

    # 遍历每个 myWallet
    for my_wallet, items in grouped_data.items():
        # 遍历该 myWallet 下的每个 followWallet 数据项
        token_info_list =  extract_token_info(fetch_wallet_assets(my_wallet))
        for item in items:
            follow_wallet = item['followWallet']
            tokens = item['tokens']
            total_pnl = sum(token_info_list.get(token, 0) for token in tokens)
            if total_pnl < -2:#删除亏损钱包，添加到只跟卖任务中
                print(tokens)
                loss_message = f"24小时内亏损 {total_pnl:.2f} sol! "
                del_message = update_targetId(follow_wallet, item['configId'],update_type='del')
                if del_message:
                    if "成功" in del_message:
                        print(loss_message + del_message)
                        send_message_via_telegram(loss_message + del_message)                        
                else:
                    configName = item['configName']
                    del_fail = loss_message + f"从{configName} 删除 {follow_wallet} 失败，请检查原因!"
                    send_message_via_telegram(del_fail)
                    print(del_fail)
                
                disabled_id = get_disabled_buy_task_ids(my_wallet,item['configName'])
                if disabled_id:
                    add_message = update_targetId(follow_wallet,disabled_id,update_type='add')
                    if add_message:
                        if "成功" in add_message:
                            print(loss_message + add_message)
                            send_message_via_telegram(loss_message + add_message)                    
                    else:                    
                        configName = item['configName']
                        add_fail = loss_message + f"向{configName} 添加 {follow_wallet} 失败，请检查原因!"
                        send_message_via_telegram(add_fail)
                else:
                    notid_message = loss_message +f"未找到只跟卖的任务配置，添加 {follow_wallet} 只跟卖失败，请检查原因!"
                    send_message_via_telegram(notid_message)
if __name__ == "__main__":
    main()

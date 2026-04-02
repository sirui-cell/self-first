# -*- coding: utf-8 -*-
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time
import logging
import json
import os
import config as c

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def request_data(url, params=None, data=None, method='GET', max_retries=3, retry_delay=7):

    """
    发送 GET 或 POST 请求，并处理重试和异常。

    :param url: 请求的 URL
    :param params: GET 请求的查询参数（用于 URL 参数）
    :param data: POST 请求的请求体数据（用于 JSON 数据）
    :param method: 请求方法，支持 'GET' 或 'POST'
    :param max_retries: 最大重试次数
    :param retry_delay: 每次重试的延迟时间（秒）
    :return: 响应的 JSON 数据，失败时返回空字典
    """
    for attempt in range(max_retries):
        try:
            method_upper = method.upper()
            if method_upper == 'GET':
                response = requests.get(url, headers=c.HEADERS, params=params, timeout=10)
            elif method_upper == 'POST':
                response = requests.post(url, headers=c.HEADERS, params=params, json=data, timeout=10)
            else:
                logger.error(f"不支持的请求方法: {method}")
                return {}

            response.raise_for_status()

            try:
                return response.json()
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error(f"请求失败，已达到最大重试次数: {url}")
                return {}           

#获取指定wallet的全部资产信息
def fetch_wallet_assets(wallet_address):
    """递增 page 参数，获取指定钱包的所有资产数据"""
    all_assets = []  # 存储所有资产
    page = 0  # 初始化页面编号

    while True:
        url = c.ASSET_API_URL.format(page=page,walletAddress=wallet_address)
        
        try:
            response = requests.get(url, headers=c.HEADERS)
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

#Fetch trades from the API and filter by the last `time_limit` minutes.
def fetch_trades(time_limit=30, max_retries=3, max_pages=1000):
    """
    Fetch trades from the API and filter by the last `time_limit` minutes.
    Enhanced with robust error handling, retries, and logging.
    
    Args:
        time_limit (int): Time window in minutes to filter trades (default: 30).
        max_retries (int): Maximum number of retries per request (default: 3).
        max_pages (int): Maximum number of pages to fetch (default: 100).
    Returns:
        list: List of filtered trades or empty list on critical failure.
    """
    trades = []
    params = {
        'page': 0,
        'size': 100
    }
    # 计算时间阈值（毫秒级）
    thirty_minutes_ago = datetime.now() - timedelta(minutes=time_limit)
    thirty_minutes_ago_timestamp_ms = int(thirty_minutes_ago.timestamp() * 1000)
    while True:
        # 防止分页超出限制
        if max_pages is not None and params['page'] >= max_pages:
            logging.warning(f"Reached maximum page limit of {max_pages}.")
            break
        # 请求重试机制
        response = None
        for attempt in range(max_retries):
            try:
                logging.info(f"Fetching page {params['page']} with {params['size']} items per page.")
                response = requests.get(
                    c.FETCH_TRADES_URL,
                    headers=c.HEADERS,
                    params=params,
                    timeout=10  # 10秒超时
                )
                response.raise_for_status()
                break  # 成功则跳出重试循环
            except requests.RequestException as e:
                logging.error(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logging.critical("Max retries exceeded. Aborting fetch.")
                    return trades if trades else []
        # 解析 JSON 响应
        try:
            data = response.json()
        except ValueError as e:
            logging.error(f"Failed to parse JSON response: {e}")
            return trades if trades else []
        # 验证响应结构
        trade_records = data.get('res')
        if not isinstance(trade_records, list):
            logging.error(f"Unexpected response structure: missing or invalid 'res' field. Data: {data}")
            return trades if trades else []
        if not trade_records:
            logging.info("No more trade records returned. Ending fetch.")
            break
        # 过滤交易记录
        filtered_trades = []
        for trade in trade_records:
            create_at = trade.get('createAt')
            if create_at is None:
                logging.warning("Trade missing 'createAt' field. Skipping.")
                continue
            try:
                create_at_ms = int(create_at)
            except (ValueError, TypeError):
                logging.warning(f"Invalid 'createAt' value: {create_at}. Skipping.")
                continue
            if create_at_ms >= thirty_minutes_ago_timestamp_ms:
                filtered_trades.append(trade)
        if not filtered_trades:
            logging.info("No trades found within the time limit in current page. Ending fetch.")
            break
        trades.extend(filtered_trades)
        params['page'] += 1
    return trades
    
#从指定任务中添加或删除 targetId。
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
    if config_id in c.Pardon:
        logging.info(f"免死 {config_id}。")
        return 0
        
    while True:
        try:
            # 发送 GET 请求
            response = requests.get(
                c.FOLLOW_ORDERS_API_URL,
                headers=c.HEADERS,
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
                                c.EDIT_FOLLOW_ORDER_URL,
                                headers=c.HEADERS,
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

def add_targetId(targetId):
    params = {
        'page': 0,
        'size': 20
        }
    target_res = get_targetIds()
    if targetId in target_res:
        print(f'{targetId} 已存在，无需添加')
        return 0
    found = False
    while True:       
        response = request_data(
                url=c.FOLLOW_ORDERS_API_URL,
                params=params,
                method="GET"
            )
        data = response

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
            targetIds = a.get("targetIds")
            taskname = a.get("name")
            if len(targetIds)<10 and targetId not in targetIds and "跟卖" not in taskname :
                # 找到目标配置
                found = True
                try:
                    a["targetIds"].append(targetId)                 
                    post_response = requests.post(
                                                    EDIT_FOLLOW_ORDER_URL,
                                                    headers=HEADERS,
                                                    json=a,
                                                    timeout=10
                                                    )
                    post_response.raise_for_status()
                    post_data = post_response.json()                       
                    if post_data.get('err'):
                        error_msg = post_data.get('msg', '未知错误')
                        logging.error(f"服务器返回错误: {error_msg}")
                except Exception as inner_e:
                    logging.error(f'处理任务 {a["name"]} 时发生异常: {inner_e}')
                    return 0                
                print(f'任务 {taskname} 添加 {targetId} 成功')
                break
        if found:
            break
        # 继续下一页
        params['page'] += 1
    

#get task by configId
def get_task_by_configid(configid):

    params = {
        'page': 0,
        'size': 20
        }

    while True:       
        response = request_data(
                url=c.FOLLOW_ORDERS_API_URL,
                params=params,
                method="GET"
            )
        data = response

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
            if current_id == configid:
                # 找到目标配置
                current_name = a
                return current_name
        # 继续下一页
        params['page'] += 1

    # 所有页面遍历完成，未找到 config_id
    logging.info(f"未找到配置 ID {configid}。")
    return 0

#get 只sell的configId by wallet_address and configName
def get_disabled_buy_task_ids(wallet_address, configName):
    """
    根据指定的 wallet address，返回 buySettings.enabled 为 False 的任务的 id 列表。

    """
    params = {
        'page': 0,
        'size': 20
    }
    
    try:
        while True:
            response = request_data(
                    url=c.FOLLOW_ORDERS_API_URL,
                    params=params,
                    method="GET"
                )
            data = response
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
                name = item.get('name')

                if not isinstance(buy_settings, dict):
                    continue  # buySettings 不是字典，跳过

                enabled = buy_settings.get('enabled')

                if wa == wallet_address and enabled is False and configName in name:
                    return item.get('id')


            params['page'] += 1

    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {e}")
        return 0
    except ValueError as e:
        logger.error(f"JSON 解析失败: {e}")
        return 0
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return 0
        
#分析指定记录，按指定格式返回快速进出的记录
def find_fast_traders(trade_data):
    """
    从跟随交易记录中找出快买快卖（买入和卖出时间间隔在5分钟内）的 copy wallet address，
    并统计其在每个 configId 下的交易对数量，返回满足条件的记录。
    """
    records = trade_data
    result = []

    # Step 1: 按 (configId, copy_wallet, wallet) 分组
    groups = defaultdict(list)
    for record in records:
        config_id = record.get('configId')
        wallet = record.get('wallet')  # 主钱包地址
        follow = record.get('follow', {})
        copy_wallet = follow.get('wallet')  # 被跟随的钱包地址
        pair = record.get('pair')
        trade_type = record.get('type')
        timestamp = record.get('timestamp')

        if not config_id or not copy_wallet or not pair or not trade_type or not timestamp:
            continue  # 跳过无效数据

        key = (config_id, copy_wallet, wallet)
        groups[key].append({
            'pair': pair,
            'type': trade_type,
            'timestamp': timestamp
        })

    # Step 2: 遍历每个分组，判断是否存在快买快卖行为
    for (config_id, copy_wallet, wallet), trades in groups.items():
        pair_dict = defaultdict(list)
        for trade in trades:
            pair_dict[trade['pair']].append(trade)

        fast_pairs = 0
        for pair, trade_list in pair_dict.items():
            buy_times = []
            sell_times = []

            for trade in trade_list:
                if trade['type'] == 'buy':
                    buy_times.append(trade['timestamp'])
                elif trade['type'] == 'sell':
                    sell_times.append(trade['timestamp'])

            buy_times.sort()
            sell_times.sort()

            i = 0
            j = 0
            found = False
            while i < len(buy_times) and j < len(sell_times):
                buy_time = buy_times[i]
                sell_time = sell_times[j]

                if sell_time < buy_time:
                    j += 1
                elif sell_time - buy_time <= c.holdtimes:#设定快进快出标准
                    found = True
                    break
                else:
                    i += 1

            if found:
                fast_pairs += 1

        if fast_pairs >= c.fast_pairs_count:
            result.append({
                "copy wallet address": copy_wallet,
                "configId": config_id,
                "wallet address": wallet,
                "fast_trade_count": fast_pairs
            })

    return result

def get_wallets():
    wallets = []  # 存储所有wallets
    params = {
        'type': 'solana',
        'page': 0,
        'size': 20
                    }

    while True:        
        response = request_data(
                url=c.wallets_URL,
                params=params,
                method="GET"
            )
        data = response

        # 获取响应中的数据列表
        tmp = data.get('res', [])
        if not isinstance(tmp, list):
            logging.error("API 返回的 'res' 字段不是列表")
            return 0

        if not tmp:
            # 没有更多数据，退出循环
            logging.info("没有更多数据，退出循环")
            break
        wallets.extend(tmp)
          
        # 继续下一页
        params['page'] += 1
        time.sleep(3)

    return wallets  # 返回所有wallets

#获取tasks
def get_tasks():
    '''
        get task
    '''
    params = {
        'page': 0,
        'size': 20
    }
    result = []
    while True:
        response = request_data(
                url=c.FOLLOW_ORDERS_API_URL,
                params=params,
                method="GET"
            )
        data = response
        # 获取响应中的数据列表
        tmp = data.get('res', [])
        if not isinstance(tmp, list):
            logging.error("API 返回的 'res' 字段不是列表")
            return 0
        if not tmp:
            # 没有更多数据，退出循环
            logging.info("没有更多数据，退出循环")
            break
        result.extend(tmp)

        params['page'] += 1
    return result

def get_targetIds():
    tasks = get_tasks()
    target_res = []
    for task in tasks:
        target_res.extend(task["targetIds"])
    return target_res

def buy_swap_order(pair,walletId,sol_count):
    """提交交易订单"""
    # 构建请求数据
    data = {
        "chain": "solana",
        "pair": pair,
        "walletId": walletId,
        "type": "buy",
        "priorityFee": "",
        "gasFeeDelta": 5,
        "maxFeePerGas": 100,
        "jitoEnabled": True,
        "jitoTip": 0.005,
        "maxSlippage": 0.40,
        "concurrentNodes": 2,
        "retries": 1,
        "amountOrPercent": sol_count,
        "migrateSellPercent": 0,
        "minDevSellPercent": 0,
        "devSellPercent": 0
    }

    try:
        # 发送 POST 请求
        response = requests.post(url=c.SWAP_URL, headers=c.HEADERS, json=data)
        
        if response.status_code == 200:
            print("Swap order submitted successfully.")
            print("Response:", response.json())
        else:
            print(f"Failed to submit swap order. Status code: {response.status_code}. Response: {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")    

def sell_swap_order(pair,walletId,percent):
    """提交交易订单"""
    # 构建请求数据
    data = {
        "chain": "solana",
        "pair": pair,
        "walletId": walletId,
        "type": "sell",
        "priorityFee": "",
        "gasFeeDelta": 5,
        "maxFeePerGas": 100,
        "jitoEnabled": True,
        "jitoTip": 0.005,
        "maxSlippage": 0.40,
        "concurrentNodes": 2,
        "retries": 2,
        "amountOrPercent": percent,
        "migrateSellPercent": 0,
        "minDevSellPercent": 0,
        "devSellPercent": 0
    }

    try:
        # 发送 POST 请求
        response = requests.post(url=c.SWAP_URL, headers=c.HEADERS, json=data)
        
        if response.status_code == 200:
            print("Swap order submitted successfully.")
            print("Response:", response.json())
        else:
            print(f"Failed to submit swap order. Status code: {response.status_code}. Response: {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")

def read_file(file_path):
    """
    从文件读取内容，返回去除空白行后的字符串列表。

    参数:
        file_path (str): 文件路径。

    返回:
        list: 非空行组成的列表。出错时返回空列表。
    """
    try:
        # 参数类型检查
        if not isinstance(file_path, str):
            raise TypeError("file_path 必须是字符串类型")

        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            pump = [line.strip() for line in file if line.strip()]
        return pump

    except FileNotFoundError as fnf_error:
        logging.error(f"文件未找到: {fnf_error}")
        print(f"警告: 文件未找到 - {fnf_error}")
        return []

    except PermissionError as perm_error:
        logging.error(f"没有读取权限: {perm_error}")
        print(f"错误: 没有权限读取文件 - {perm_error}")
        return []

    except UnicodeDecodeError as decode_error:
        logging.error(f"文件编码错误: {decode_error}")
        print(f"错误: 文件编码不支持，请确认是否为文本文件 - {decode_error}")
        return []

    except Exception as e:
        logging.exception(f"读取文件时发生未知错误: {e}")
        print(f"错误: 读取文件失败 - {e}")
        return []

def getNameByConfigid(configid):
    params = {
        'page': 0,
        'size': 20
        }

    while True:
        try:
            # 发送 GET 请求
            response = request_data(
                    url=c.FOLLOW_ORDERS_API_URL,
                    params=params,
                    method="GET"
                )
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
            if current_id == configid:
                # 找到目标配置
                current_name = a.get('name')
                return current_name
        # 继续下一页
        params['page'] += 1
        time.sleep(1)

    # 所有页面遍历完成，未找到 config_id
    logging.info(f"未找到配置 ID {configid}。")
    return 0  

def createTask():
    pass

if __name__ == "__main__":
    #a = '7WuMLoWj8JGK2bC7ZEXXeTAzdy4SJ6HVMaqhMHBkoLK6'
    #b = fetch_wallet_assets(a)
    #c=getNameByConfigid('mbp6wvd12ku93p')
    #d = get_disabled_buy_task_ids('7WuMLoWj8JGK2bC7ZEXXeTAzdy4SJ6HVMaqhMHBkoLK6','4等')
    #e = update_task_by_targetId('7FFUT7BPpzHCMAE1pNMDtam7uYFUq1esLsxbUSK5T6AG','mbp6wvd12ku93p','add')
    e = get_targetIds()
    for i in e:
        print(i)

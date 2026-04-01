import requests
import json
from collections import defaultdict
from datetime import datetime, timedelta
import time
import logging
import botApi as bot
import config as c

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
                    FETCH_TRADES_URL,
                    headers=HEADERS,
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
        time.sleep(1)

    return trades

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
                elif sell_time - buy_time <= 5 * 60:
                    found = True
                    break
                else:
                    i += 1

            if found:
                fast_pairs += 1

        if fast_pairs >= 2:
            result.append({
                "copy wallet address": copy_wallet,
                "configId": config_id,
                "wallet address": wallet,
                "fast_trade_count": fast_pairs
            })

    return result
 
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
                name = item.get('name')

                if not isinstance(buy_settings, dict):
                    continue  # buySettings 不是字典，跳过

                enabled = buy_settings.get('enabled')

                if wa == wallet_address and enabled is False and configName in name:
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
        
def send_message_via_telegram(message):
    """发送消息到Telegram群组"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
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

def getNameByConfigid(configid):
    params = {
        'page': 0,
        'size': 20
        }

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
                
def main():
    trades = []
    trades = fetch_trades(time_limit=30, max_retries=3, max_pages=100)
    if not trades:
        print(f"no trade in 30m")
    else:
        fast_trade = find_fast_traders(trades)
        if not fast_trade:
            print(f"no fast traders")
        else:
            for fast in fast_trade:   #{"copy wallet address":copy_wallet,"configId": config_id,"wallet address": wallet,"fast_trade_count": fast_pairs}
                fast_message = f"快速买卖 {fast['fast_trade_count']} 次!  "
                del_message = update_targetId(fast['copy wallet address'],fast['configId'],update_type='del')
                if del_message:
                    if "成功" in del_message:
                        print(del_message)
                        send_message_via_telegram(fast_message + del_message)                        
                else:
                    del_configName = getNameByConfigid(fast['configId'])
                    if del_configName:
                        del_fail = fast_message + f"从{del_configName} 删除 {fast['copy wallet address']} 失败，请检查原因!"
                        send_message_via_telegram(del_fail)
                    else:
                        send_message_via_telegram(fast_message+f"{fast['copy wallet address']} 所在的任务已删除，请检查原因! ")
                    print(del_message)
                    
                configName = getNameByConfigid(fast['configId'])
                disabled_id = get_disabled_buy_task_ids(fast["wallet address"],configName)
                if disabled_id:
                    add_configName = getNameByConfigid(disabled_id)
                    add_message = update_targetId(fast['copy wallet address'],disabled_id,update_type='add')
                    if add_message:
                        if "成功" in add_message:
                            print(add_message)
                            send_message_via_telegram(fast_message + add_message)                    
                    else:                    
                        
                        add_fail = fast_message + f"向{add_configName} 添加 {fast['copy wallet address']} 失败，请检查原因!"
                        send_message_via_telegram(add_fail)
                        print(add_fail)
                else:
                    notid_message = fast_message +f"未找到只跟卖的任务配置，添加 {fast['copy wallet address']} 只跟卖失败，请检查原因!"
                    send_message_via_telegram(notid_message)
                   

if __name__ == "__main__":
    main()

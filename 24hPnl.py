import requests
import concurrent.futures
import threading
import os
import time

HEADERS = {
    'X-API-KEY': 'yourtoken'
}

GET_WALLETS = "https://api-bot-v1.dbotx.com/account/wallets?type={type}&page={page}&size={size}"
ASSET_API_URL = "https://servapi.dbotx.com/account/wallet/assets?chain=solana&page={page}&size=20&walletAddress={wallet_address}&sortBy=value&minValueUsd=0.001"

# 发送消息到 Telegram
BOT_TOKEN = "yourtoken"  # 替换为你的Bot Token
CHAT_ID = 7096464619     # 替换为你的群组Chat ID


#get wallets_info:列表[{'id': 'mb0d3w78bijds9', 'name': '3号', 'type': 'solana', 'address': '2CmLCD', 'sort': 0, '_id': 'mb0d3w78bijds9'},...]
def walletInfo(api_url, wallet_type="solana"):
    """获取所有钱包地址"""
    wallets = []
    page = 0
    while True:
        try:
            url = api_url.format(type=wallet_type,page=page,size=20)
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            if data and "res" in data and data["res"]:
                wallets.extend(data["res"])  # 添加当前页的wallets
                page += 1  # 递增页面编号
            else:
                break  # 如果没有wallets，退出循环

        except requests.RequestException as e:
            print(f"请求失败: {e}")  
    return wallets
        
#get assets of the wallet:[{'_id': '', 'token': 'pump', 'tokenBalance': '10122292207861', 'tokenBalanceUI': '10122292.207861', 'tokenPriceSOL': 2.9473812148303204e-07, 'tokenPriceUsd': 4.672483439870507e-05, 'hold': 2.9834253904472843, 'cost': 0.856758321, 'sold': 0, 'pnl': 2.1266670694472842, 'pnlPercent': 2.4822251705300733, 'buyTimes': 1, 'sellTimes': 0, 'avgBuyPrice': 8.464074178125773e-08, 'avgBuyPriceUsd': 1.3418096794582787e-05, 'avgSellPrice': None, 'avgSellPriceUsd': 0, 'tokenInfo': {'contract': 'pump', 'name': 'SCAMMING ASS KAVELL', 'symbol': '$SAK', 'icon': '', 'decimals': 6, 'totalSupply': '1000000000000000', 'tokenProgram': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', 'mintAuthority': None, 'freezeAuthority': None, 'createAt': 1749514255210}, 'currencyInfo': {'contract': '', 'name': 'Wrapped SOL', 'symbol': 'SOL', 'decimals': 9, 'icon': '', 'totalSupply': None}, 'links': {'dexscreener': ''}, 'limitOrderCount': 0, 'pnlCountByFollowOrder': 0, 'pnlCountBySwapOrder': 0, 'trailingCountByFollowOrder': 0, 'trailingCountBySwapOrder': 0},...]
def assetsInfo(wallet_address):
    """递增 page 参数，获取指定钱包的所有资产数据"""
    all_assets = []  # 存储所有资产
    page = 0  # 初始化页面编号

    while True:
        url = ASSET_API_URL.format(wallet_address=wallet_address, page=page)
        
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()  # 检查请求是否成功
            data = response.json()  # 返回 JSON 数据
            
            # 检查是否有资产数据
            if data and "res" in data and data["res"]:
                all_assets.extend(data["res"])  # 添加当前页的资产数据
                page += 1  # 递增页面编号
            else:
                break  # 如果没有资产，退出循环

        except requests.RequestException as e:
            print(f"请求失败: {e}")
            time.sleep(2)

    return all_assets  # 返回所有资产数据

#get lambda:{'2CH': 0.034335726, '876': 0.152984145, '8FJ': 0.119644698, '7W': 4.903612034}

def lamportsInfo(wallet_list):
    url = 'https://mainnet.helius-rpc.com/?api-key=d09a4ecd-04fc-4efb-8a2f-dcc491b72cdf'
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.140 Safari/537.36",
        "Accept": "*/*",
    }
    
    payload = {
        "method": "getMultipleAccounts",
        "jsonrpc": "2.0",
        "params": [
            wallet_list,
            {"encoding": "base64"}
        ],
        "id": "390cb241-9400-4218-a68d-3ab21e689db7"
    }
    
    lamport_dict = {}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 检查请求是否成功
        
        result = response.json()
        lamports = [account['lamports'] / 1_000_000_000 for account in result['result']['value']]
        
        lamport_dict = {wallet_list[i]: round(lamports[i],2) for i in range(len(wallet_list))}
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")

    return lamport_dict

def get_HoldAsset(wallet_address):
    """
    获取指定钱包地址中所有资产的 hold 值总和。
    如果任何环节出错，返回 0。
    """
    try:
        # 获取资产信息，捕获可能的异常
        assets = assetsInfo(wallet_address)
    except Exception as e:
        print(f"获取资产信息失败: {e}")
        return 0

    total_hold = 0

    # 确保 assets 是一个列表
    if isinstance(assets, list):
        for asset in assets:
            # 确保每个 asset 是字典
            if isinstance(asset, dict):
                # 获取 hold 值，尝试转换为浮点数
                hold = asset.get("hold")
                try:
                    total_hold += float(hold)
                except (TypeError, ValueError):
                    # 忽略无法转换为数字的 hold 值
                    pass

    return total_hold

def get_Lamport(wallet_address,lamports):
    return lamports[wallet_address]

    
def write_wallet_pnl_to_file(filename, wallet_pnl):
    """将每个钱包的总资产写入文件"""
    with open(filename, 'w') as file:
        for wallet, pnl in wallet_pnl.items():
            file.write(f"{wallet}:{pnl}\n")

def read_wallet_pnl_from_file(filename):
    """从指定文件中读取每个钱包的总资产值"""
    wallet_pnl = {}
    try:
        with open(filename, 'r') as file:
            for line in file:
                wallet, pnl = line.strip().split(':')
                wallet_pnl[wallet] = float(pnl)  # 转换为浮点数
    except FileNotFoundError:
        print(f"错误: 文件 '{filename}' 未找到。")
    except ValueError:
        print("错误: 文件内容格式错误，无法转换为数字。")
    return wallet_pnl

def fetch_trades(time_limit = 24):
    trades = []
    api_url = "https://servapi.dbotx.com/account/follow_trades"
    params = {
        "chain": "",
        "page": 0,
        "size": 100 # Larger size to reduce number of requests
    }
    
    while True:
        try:
            response = requests.get(api_url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            trade_records = data.get('res', [])

            if not trade_records:
                break

            recent_trades = filter_recent_trades(trade_records, time_limit)
            trades.extend(recent_trades)
            if not recent_trades:
                break

            params['page'] += 1
        except requests.RequestException as error:
            print(f"Error fetching data: {error}")
            break
    return trades
#获取指定时间（小时）内的成功trades，返回列表[{wallet:'',targetWallet:'',type:'',configId:'',configName:''},...]
def filter_recent_trades(trade_records, time_limit):
    filtered_trades = []
    current_time = time.time()
    for trade in trade_records:
        if trade['state'] == 'done':
            timestamp = trade.get('createAt')
            if timestamp:
                try:
                    if (timestamp / 1000) > current_time - time_limit * 60 * 60:
                        follow_info = trade.get("follow")
                        targetWallet = follow_info.get("wallet")
                        filtered_trades.append({
                            "wallet": trade.get("wallet"),
                            "targetWallet": targetWallet,
                            "type": trade.get("type"),
                            "configId":trade.get("configId"),
                            "configName":trade.get("configName")
                        })
                except (ValueError, TypeError) as e:
                    print(f"Error processing timestamp {timestamp}: {e}")
    return filtered_trades

def count_wallet_transactions(transactions):
    """
    统计每个钱包的买入和卖出次数。

    :param transactions: 包含交易信息的列表，每个元素是一个字典，包含 'wallet'、'targetWallet' 和 'type' 字段。
    :return: 一个字典，格式为 {wallet: 'buy/sell', ...}，表示每个钱包的买入和卖出次数。
    """
    wallet_counts = {}

    for tx in transactions:
        wallet = tx['wallet']
        tx_type = tx['type']

        if wallet not in wallet_counts:
            wallet_counts[wallet] = {'buy': 0, 'sell': 0}

        if tx_type == 'buy':
            wallet_counts[wallet]['buy'] += 1
        elif tx_type == 'sell':
            wallet_counts[wallet]['sell'] += 1

    # 将结果格式化为字符串形式
    result = {wallet: f"{counts['buy']}/{counts['sell']}" for wallet, counts in wallet_counts.items()}

    return result

#get target_wallet count of buy/sell sort by desc
def count_target_wallet_transactions(transactions):
    """
    统计每个 targetWallet 的买入和卖出次数，并按总交易次数从大到小排序。
    返回结果中包含对应的 configName。

    :param transactions: 包含交易信息的列表，每个元素是一个字典，包含以下字段：
                         'targetWallet', 'type', 'configName'
    :return: 一个字典，格式为 {targetWallet: 'buy/sell configName', ...}，
             按总交易次数降序排列。
    """
    counts = {}

    for tx in transactions:
        target = tx['targetWallet']
        tx_type = tx['type']
        config_name = tx['configName']

        if target not in counts:
            counts[target] = {
                'buy': 0,
                'sell': 0,
                'configName': config_name
            }

        if tx_type == 'buy':
            counts[target]['buy'] += 1
        elif tx_type == 'sell':
            counts[target]['sell'] += 1

    # 按总交易次数（buy + sell）降序排序
    sorted_targets = sorted(
        counts.items(),
        key=lambda item: item[1]['buy'] + item[1]['sell'],
        reverse=True
    )

    # 构造最终结果，附加 configName
    result = {
        target: f"{item['buy']}/{item['sell']} {item['configName']}"
        for target, item in sorted_targets
    }

    return result

def count_buy_sell(tasks):
    buy_count = 0
    sell_count = 0

    for item in tasks:
        task_type = item.get('type')
        if task_type == 'buy':
            buy_count += 1
        elif task_type == 'sell':
            sell_count += 1

    return f"{buy_count}/{sell_count}"

def get_targetWallets():
    target_ids = []
    api_url="https://api-bot-v1.dbotx.com/automation/follow_orders"
    params = {
        "chain": 'solana',
        "page": 0,
        "size": 100 # Larger size to reduce number of requests
    }
    while True:
        try:
            response = requests.get(api_url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            tasks = data.get('res', [])   

            if not tasks:
                break
            
            for task in tasks:
                buy_set = task.get('buySettings')
                if  buy_set.get("enabled"):
                    target_ids.extend(task.get('targetIds', []))

            params['page'] += 1
        except requests.RequestException as error:
            print(f"Error fetching data: {error}")
            break
    with open('target_wallet.txt', 'w', encoding='utf-8') as f:
        for id in target_ids:
            f.write(id + '\n')
    return target_ids
    
def send_message_via_telegram(bot_token, chat_id, message):
    """发送消息到Telegram群组"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"HTTP错误: {err}")
    except Exception as err:
        print(f"发生错误: {err}")

#根据wallet的address获取name
def getNameByAddr(wallet_address,wallets):
    for wallet in wallets:
        if wallet['address'] == wallet_address:
            name = wallet['name']
    return name
    
def main():
    """主函数"""
    trades_24h = fetch_trades(24)#get trade_info in 24h
    count_BuyAndSell = count_buy_sell(trades_24h)
    transactions = count_wallet_transactions(trades_24h)
    targetWallet_transactions = count_target_wallet_transactions(trades_24h) #get target_wallet count of buy/sell sort by desc
    
    active_wallet_count = len(targetWallet_transactions) #活跃的targetwallets数
    
    targetIds = get_targetWallets()#总的targetIds
    total_copyWallets = len(targetIds)
    
    active_rate = round(active_wallet_count/total_copyWallets,2)#跟单targetIds活跃率，24h内有触发
    
    wallet_Trade_24h = []
    wallets = walletInfo(GET_WALLETS) #获取wallet信息
    wallet_list = [wallet['address'] for wallet in wallets] #获取wallet_list
    lamports = lamportsInfo(wallet_list) #获取每个wallet的lamports
    wallet_hold = {wallet:round(get_HoldAsset(wallet),2) for wallet in wallet_list} #获取每个wallet的持仓资产
    wallet_totalAsset = {wallet:round(lamports[wallet]+get_HoldAsset(wallet),2) for wallet in wallet_list} #获取每个wallet的总资产
    if os.path.exists("wallet_totalAsset.txt"):
        wallet_totalAsset_24h_ago = read_wallet_pnl_from_file("wallet_totalAsset.txt")
        wallet_pnl = {wallet:round((wallet_totalAsset[wallet]-wallet_totalAsset_24h_ago[wallet])/wallet_totalAsset_24h_ago[wallet],2) for wallet in wallet_list} #计算每个wallet在24h内的pnl
        trade_count = '0/0'
        for wallet in wallet_list:
            trade_info = getNameByAddr(wallet,wallets) + '  ' + str(wallet_hold[wallet]) + '  ' + str(lamports[wallet]) + '  ' + str(wallet_pnl[wallet]) + '  ' + transactions.get(wallet,'0/0')
            wallet_Trade_24h.append(trade_info)
            
        #发送信息telegram
        message = "\n".join(wallet_Trade_24h)
        targetWallet_message = "\n----\n".join([f"{k}:  {v}" for k, v in targetWallet_transactions.items()])
        #wallet tradeInfo in 24h
        full_message = (
            f"24H 利润汇总\n"
            f"钱包  hold  bal  Pnl  buy/sell\n"
            f"==============================\n"
            f"{message}"
        )
        #targetWallet tradeInfo in 24h
        full_message2 = (
            f"buy/sell : {count_BuyAndSell}  active_wallet:{active_wallet_count}  {active_rate}\n"
            f"==============================\n"
            f"{targetWallet_message}"
        )
        write_wallet_pnl_to_file("wallet_totalAsset.txt", wallet_totalAsset)
        #send_message_via_telegram(BOT_TOKEN, CHAT_ID, full_message)
        #send_message_via_telegram(BOT_TOKEN, CHAT_ID, full_message2)
        print(full_message)
    else:
        write_wallet_pnl_to_file("wallet_totalAsset.txt",wallet_totalAsset)
if __name__ == "__main__":
    main()

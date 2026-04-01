# -*- coding: utf-8 -*-

import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time
import logging
import json
import config as c
import botApi as bot

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        data = bot.request_data(c.FETCH_TRADES_URL, params=params)
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
        token_info_list =  extract_token_info(bot.fetch_wallet_assets(my_wallet))
        for item in items:
            follow_wallet = item['followWallet']
            tokens = item['tokens']
            total_pnl = sum(token_info_list.get(token, 0) for token in tokens)
            if total_pnl < c.sumLoss:#删除亏损钱包，添加到只跟卖任务中
                print(tokens)
                loss_message = f"24小时内亏损 {total_pnl:.2f} sol! "
                del_message = bot.update_targetId(follow_wallet, item['configId'],update_type='del')
                if del_message:
                    if "成功" in del_message:
                        print(loss_message + del_message)
                        c.send_message_via_telegram(loss_message + del_message)                        
                else:
                    configName = item['configName']
                    del_fail = loss_message + f"从{configName} 删除 {follow_wallet} 失败，请检查原因!"
                    c.send_message_via_telegram(del_fail)
                    print(del_fail)
                
                disabled_id = bot.get_disabled_buy_task_ids(my_wallet,item['configName'])
                if disabled_id:
                    add_message = bot.update_targetId(follow_wallet,disabled_id,update_type='add')
                    if add_message:
                        if "成功" in add_message:
                            print(loss_message + add_message)
                            c.send_message_via_telegram(loss_message + add_message)                    
                    else:                    
                        configName = item['configName']
                        add_fail = loss_message + f"向{configName} 添加 {follow_wallet} 失败，请检查原因!"
                        c.send_message_via_telegram(add_fail)
                else:
                    notid_message = loss_message +f"未找到只跟卖的任务配置，添加 {follow_wallet} 只跟卖失败，请检查原因!"
                    c.send_message_via_telegram(notid_message)
if __name__ == "__main__":
    main()

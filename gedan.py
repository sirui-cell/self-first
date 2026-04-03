import sys
import os
import time
import json
import requests
import botApi as bot

HEADERS = {
    'X-API-KEY': 'yourtoken'
}
pumpfile = 'gedan_pump.txt'
sol_count = 0.1
percent = 1

def main():
    pump_list = bot.read_file(pumpfile)
    wallets = bot.get_wallets()
    walletId = wallets[0]['id']
    for i in range(0, len(pump_list), 10):
        # 获取当前批次
        batch = pump_list[i:i+10]
        print(batch)
        # 购买当前批次
        for token in batch:
            bot.buy_swap_order(token,walletId,sol_count)
            time.sleep(1)

        # 持有 1 分钟
        print("Holding tokens for 1 minute...")
        time.sleep(3)

        # 卖出当前批次的
        for token in batch:
            bot.sell_swap_order(token,walletId,percent)
            time.sleep(1)

        # 等待 1 分钟再进行下一批次的购买
        print("Waiting for 1 minute before the next batch...")
        time.sleep(5)

if __name__ == "__main__":
    main()
    



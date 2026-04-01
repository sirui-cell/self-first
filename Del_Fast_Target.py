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
               
def main():
    trades = []
    trades = bot.fetch_trades(time_limit=30, max_retries=3, max_pages=1000)
    if not trades:
        print(f"no trade in 30m")
    else:
        fast_trade = bot.find_fast_traders(trades)
        if not fast_trade:
            print(f"no fast traders")
        else:
            for fast in fast_trade:   #{"copy wallet address":copy_wallet,"configId": config_id,"wallet address": wallet,"fast_trade_count": fast_pairs}
                fast_message = f"快速买卖 {fast['fast_trade_count']} 次!  "
                del_message = bot.update_targetId(fast['copy wallet address'],fast['configId'],update_type='del')
                if del_message:
                    if "成功" in del_message:
                        print(del_message)
                        c.send_message_via_telegram(fast_message + del_message)                        
                else:
                    del_configName = bot.getNameByConfigid(fast['configId'])
                    if del_configName:
                        del_fail = fast_message + f"从{del_configName} 删除 {fast['copy wallet address']} 失败，请检查原因!"
                        c.send_message_via_telegram(del_fail)
                    else:
                        c.send_message_via_telegram(fast_message+f"{fast['copy wallet address']} 所在的任务已删除，请检查原因! ")
                    print(del_message)
                    
                configName = bot.getNameByConfigid(fast['configId'])
                disabled_id = bot.get_disabled_buy_task_ids(fast["wallet address"],configName)
                if disabled_id:
                    add_configName = bot.getNameByConfigid(disabled_id)
                    add_message = bot.update_targetId(fast['copy wallet address'],disabled_id,update_type='add')
                    if add_message:
                        if "成功" in add_message:
                            print(add_message)
                            c.send_message_via_telegram(fast_message + add_message)                    
                    else:                    
                        
                        add_fail = fast_message + f"向{add_configName} 添加 {fast['copy wallet address']} 失败，请检查原因!"
                        c.send_message_via_telegram(add_fail)
                        print(add_fail)
                else:
                    notid_message = fast_message +f"未找到只跟卖的任务配置，添加 {fast['copy wallet address']} 只跟卖失败，请检查原因!"
                    c.send_message_via_telegram(notid_message)
                   

if __name__ == "__main__":
    main()

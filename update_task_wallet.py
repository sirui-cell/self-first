import time
import logging
import json
import requests
import botApi as bot
import config as c

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_walletId_by_walletName(wallets, walletName):
    """
    根据 walletName 返回对应的 walletId（即 '_id' 字段）

    :param wallets: 钱包列表，格式为包含字典的列表
    :param walletName: 要查找的钱包名称
    :return: 匹配到的钱包的 '_id'，未找到则返回 None
    """
    for wallet in wallets:
        if not isinstance(wallet, dict):
            continue
        if wallet.get("name") == walletName:
            return wallet.get("_id")
    return None

def fetch_tasks(page, size):
    """
    获取任务列表
    """
    try:
        logger.info(f"正在获取第 {page} 页的任务列表，每页 {size} 条")
        response = requests.get(
            c.FOLLOW_ORDERS_API_URL,
            headers=c.HEADERS,
            params={"page": page, "size": size},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"获取任务列表失败: {e}")
        return None

def update_task(task, walletA, walletB):
    """
    如果 walletAddress 是 walletA，则更新为 walletB
    """
    if task.get("walletId") != walletA:
        return False

    logger.info(f"发现匹配地址的任务: {task.get('name')}")
    task["walletId"] = walletB

    try:
        logger.info(f"正在更新任务 {task.get('name')} 的 walletAddress 为 {walletB}")
        response = requests.post(
            c.EDIT_FOLLOW_ORDER_URL,
            headers=c.HEADERS,
            json=task,
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"任务 {task.get('name')} 更新成功")
        print('------------')
        return True
    except requests.RequestException as e:
        logger.error(f"更新任务 {task.get('name')} 失败: {e}")
        return False

def update_task_wallet(walletA, walletB):
    """
    主函数：遍历所有任务页，更新 walletAddress
    """
    page = 0
    size = 20
    updated_count = 0

    while True:
        data = fetch_tasks(page, size)
        if not data or data.get("err") is not False:
            logger.error("API 返回错误或无数据")
            break

        tasks = data.get("res", [])
        if not isinstance(tasks, list):
            logger.error("API 返回的 'res' 字段不是列表")
            break

        if not tasks:
            logger.info("没有更多任务，退出循环")
            break

        for task in tasks:
            if not isinstance(task, dict):
                logger.warning("发现非字典格式的任务，跳过")
                continue

            if update_task(task, walletA, walletB):
                updated_count += 1

        page += 1

    logger.info(f"任务更新完成，共更新了 {updated_count} 个任务的 walletAddress")
    return updated_count

def main():
    wallets = bot.get_wallets()
    for wallet in wallets:
        print(f"{wallet['id']} {wallet['name']} {wallet['address']}")
    walletName_A = bot.read_file('swalletName.txt')
    walletName_B = bot.read_file('dwalletName.txt')
    i = 0
    l = len(walletName_A)
    while i < l:
        walletId_A = get_walletId_by_walletName(wallets,walletName_A[i])
        walletId_B = get_walletId_by_walletName(wallets,walletName_B[i])
        logger.info(f"开始更新任务，将 walletAddress 从 '{walletName_A[i]}' 替换为 '{walletName_B[i]}'")
        print('+*******+')
        update_task_wallet(walletId_A, walletId_B)
        i += 1 
        print('==============================')
if __name__ == "__main__":
    main()

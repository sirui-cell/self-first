import botApi as bot
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def task_to_task_dict(tasks):
    """
    将任务列表转换为 {"id": ["targetIds"]} 字典，增强健壮性。
    """
    task_dict = {}

    if not isinstance(tasks, list):
        logging.warning("输入的任务数据不是一个列表，跳过处理。")
        return task_dict

    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            logging.warning(f"任务数据第 {idx + 1} 项不是一个字典，跳过。")
            continue

        task_id = task.get("id")
        target_ids = task.get("targetIds")

        if not isinstance(target_ids, list):
            logging.warning(f"任务 '{task_id}' 的 'targetIds' 不是列表，设置为空列表。")
            target_ids = []

        task_dict[task_id] = target_ids

    return task_dict

def remove_duplicate_targetIds(task_dict):
    """
    检查 targetId 是否在多个任务中重复出现，并删除重复项（保留第一个出现的任务）。
    返回处理后的 task_dict。
    """
    value_to_tasks = {}

    # 第一次遍历：记录每个 targetId 出现在哪些任务中
    for task_id, target_ids in task_dict.items():
        if not isinstance(target_ids, list):
            continue
        for target in target_ids:
            if target not in value_to_tasks:
                value_to_tasks[target] = []
            value_to_tasks[target].append(task_id)

    # 第二次遍历：对每个重复的 targetId，只保留第一个任务，其余任务中删除
    for target, task_ids in value_to_tasks.items():
        if len(task_ids) > 1:
            keep_task = task_ids[0]
            duplicates = task_ids[1:]
            logging.warning(f"targetId '{target}' 重复存在于任务 {', '.join(task_ids)} 中，保留 '{keep_task}'，删除其余任务中的该值。")

            for task_id in duplicates:
                if target in task_dict[task_id]:
                    task_dict[task_id].remove(target)
                    bot.update_targetId(target, task_id, update_type='del')

    return task_dict


def main():   
    try:
        tasks = bot.get_tasks()
    except Exception as e:
        logging.error(f"获取任务数据失败: {e}")
        return
        
    if not tasks:
        logging.info("未获取到任何任务数据。")
        return
        
    task_dict = task_to_task_dict(tasks)
    #logging.info("原始任务字典: %s", task_dict)

    # 删除重复的 targetIds
    cleaned_task_dict = remove_duplicate_targetIds(task_dict)
    #logging.info("处理后任务字典: %s", cleaned_task_dict)


if __name__ == "__main__":
    main()

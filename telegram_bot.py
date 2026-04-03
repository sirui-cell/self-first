import subprocess
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 閰嶇疆
BOT_TOKEN = "yourtoken"  # 鏇挎崲涓轰綘鐨?Bot Token
AUTHORIZED_USER_ID = 7096464619  # 鏇挎崲涓轰綘鐨?Telegram 鐢ㄦ埛 ID锛堝彲閫夛級

# 鎵ц鍛戒护鍑芥暟
async def execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 鍙€夛細闄愬埗璁块棶鏉冮檺
    if update.effective_user.id != AUTHORIZED_USER_ID:
        await update.message.reply_text("鈿狅笍 鏃犳潈闄愯闂紒")
        return

    # 鑾峰彇鍛戒护鍙傛暟锛堝 /run_script a.py锛?
    if not context.args:
        await update.message.reply_text("鉂?璇锋寚瀹氳剼鏈悕绉帮紝渚嬪锛?run_script a.py")
        return

    script_name = context.args[0]
    script_path = os.path.join(os.path.dirname(__file__), script_name)

    if not os.path.exists(script_path):
        await update.message.reply_text(f"鉂?鑴氭湰 {script_name} 涓嶅瓨鍦紒")
        return

    try:
        # 鎵ц鑴氭湰骞舵崟鑾疯緭鍑?
        result = subprocess.check_output(
            ["python", script_path],
            stderr=subprocess.STDOUT,
            timeout=120,
            text=True
        )
        await update.message.reply_text(f"鉁?鎵ц鎴愬姛锛歕n```\n{result}\n```", parse_mode="Markdown")
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"鉂?鑴氭湰鎵ц澶辫触锛歕n```\n{e.output}\n```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"鈿狅笍 绯荤粺閿欒锛歿str(e)}")

# 鍚姩鍑芥暟
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("馃 鏈哄櫒浜哄凡鍚姩锛佸彂閫?/run <鑴氭湰鍚? 鎵ц鍛戒护銆?)

# 涓诲嚱鏁?
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 娉ㄥ唽鍛戒护
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", execute_command))
    
    # 鍚姩鏈哄櫒浜?
    print("馃殌 鏈哄櫒浜哄凡鍚姩锛岀瓑寰呭懡浠?..")
    app.run_polling()

if __name__ == "__main__":
    main()

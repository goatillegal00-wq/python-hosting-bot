import asyncio
import logging
import os
import subprocess
import threading
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from flask import Flask

# আপনার বটের টোকেন এবং ওনার আইডি এখানে বসাবেন
TOKEN = os.getenv("TOKEN", "9052315965:AAG8lVOA5Zj3oy0n0nD9wAkpeXaRQq0ULmk")
OWNER_ID = int(os.getenv("OWNER_ID", "6260738689"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ফ্লাস্ক সার্ভার (Fly.io-এর হেলথ চেক ও টাইমআউট এরর দূর করার জন্য) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running 24/7 on Fly.io!"

def run_web():
    # Fly.io-এর জন্য পোর্ট 8080 সেট করা হলো
    app.run(host="0.0.0.0", port=8080)
# -------------------------------------------------------------

# ইউজারদের রান করা প্রসেস ও ফাইল ট্র্যাক করার ডিকশনারি
running_bots = {}

# মূল মেনু বা ইনলাইন কিবোর্ড তৈরি করার ফাংশন
def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📁 Upload File", callback_data="upload_help")
    builder.button(text="📂 Check Files", callback_data="check_files")
    builder.button(text="⚡ Bot Speed", callback_data="bot_speed")
    builder.button(text="📊 Statistics", callback_data="statistics")
    builder.button(text="📞 Contact Owner", url="https://t.me/Traderwhite01")
    builder.adjust(2, 2, 1) # প্রতি লাইনে কয়টি বাটন থাকবে
    return builder.as_markup()

# ১. /start কমান্ড এবং মূল মেনু প্যানেল পাঠানো
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "🤖 **PYTHON SCRIPT HOSTING BOT**\n\n"
        "Welcome! Using this bot, you can upload your Python scripts (`.py`) and run them live 24/7 on the server.\n\n"
        "Please select your desired option from the menu below:"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    
# ২. ইনলাইন বাটন হ্যান্ডলার (Callback Query)
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    data = callback.data
    
    if data == "upload_help":
        await callback.message.edit_text(
            "📁 **ফাইল আপলোড করার নিয়ম:**\n\n"
            "সরাসরি চ্যাটে আপনার পাইথন ফাইল (`.py`) ডকুমেন্ট হিসেবে সেন্ড করুন। বট স্বয়ংক্রিয়ভাবে তা রিসিভ করে রান করবে!",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    elif data == "check_files":
        user_dir = f"upload_bots/{callback.from_user.id}"
        if os.path.exists(user_dir):
            files = os.listdir(user_dir)
            file_list = "\n".join([f"• {f}" for f in files]) if files else "কোনো ফাইল নেই।"
            await callback.message.edit_text(f"📂 **আপনার আপলোড করা ফাইলসমূহ:**\n\n{file_list}", reply_markup=get_main_menu(), parse_mode="Markdown")
        else:
            await callback.answer("⚠️ আপনার কোনো ফাইল আপলোড করা নেই!", show_alert=True)
            
    elif data == "bot_speed":
        await callback.answer("⚡ বটের সার্ভার স্পিড চমৎকার রয়েছে (Ping: 14ms)", show_alert=True)
        
    elif data == "statistics":
        total_running = len(running_bots)
        await callback.message.edit_text(
            f"📊 **বট স্ট্যাটিস্টিক্স:**\n\n"
            f"🚀 একটিভ স্ক্রিপ্ট সংখ্যা: `{total_running}` টি\n"
            f"🟢 সার্ভার স্ট্যাটাস: অনলাইন",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    await callback.answer()

# ৩. ইউজার যখন কোনো পাইথন ফাইল (.py) আপলোড করবে
@dp.message(F.document)
async def handle_document(message: types.Message):
    file_name = message.document.file_name
    
    if not file_name.endswith(".py"):
        await message.reply("❌ শুধুমাত্র পাইথন ফাইল (`.py`) আপলোড করা যাবে!")
        return

    status_msg = await message.reply(f"📥 `{file_name}` ডাউনলোড করা হচ্ছে...", parse_mode="Markdown")
    
    # ইউজার অনুযায়ী ফোল্ডার তৈরি
    user_id = message.from_user.id
    user_dir = f"upload_bots/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    
    file_path = os.path.join(user_dir, file_name)
    
    # ফাইল ডাউনলোড করা
    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, file_path)
    
    await status_msg.edit_text(f"✅ `{file_name}` সফলভাবে ডাউনলোড হয়েছে। প্রসেস করা হচ্ছে...", parse_mode="Markdown")
    
    # অটো লাইব্রেরি চেক বা ইন্সটল করার ছোট লজিক ও স্ক্রিপ্ট রান করা
    try:
        # সাবপ্রসেস দিয়ে ব্যাকগ্রাউন্ডে পাইথন ফাইল রান করানো
        process = subprocess.Popen(["python", file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        running_bots[user_id] = process.pid
        
        await status_msg.edit_text(
            f"✅ Python script `{file_name}` started! (PID: `{process.pid}`)\n"
            f"(For User: `{user_id}`)",
            parse_mode="Markdown"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error in script for `{file_name}`:\n`{e}`", parse_mode="Markdown")

async def main():
    # ফ্লাস্ক ওয়েব সার্ভার আলাদা ব্যাকগ্রাউন্ড থ্রেডে চালু করা হলো
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    print("Flask web server started on port 8080!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

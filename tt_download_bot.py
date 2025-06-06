import logging
import os
import uuid
import subprocess
from re import findall

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from tt_video import yt_dlp
from settings import languages, API_TOKEN

storage = MemoryStorage()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

ADMIN_ID = 1115310967

def is_tool(name):
    from shutil import which
    return which(name) is not None

def get_user_lang(locale):
    if locale and hasattr(locale, 'language'):
        return locale.language if locale.language in languages else "en"
    return "en"

TIKTOK_REGEX = r'https://(vm\.tiktok\.com|vt\.tiktok\.com|www\.tiktok\.com)/\S+'
YTSHORTS_REGEX = r'https://(www\.)?youtube\.com/shorts/[^\s?]+'
VK_REGEX = r'https://(www\.)?vk\.com/(video|clip)[\w/-]+'

def is_supported_link(text: str) -> bool:
    return bool(
        findall(TIKTOK_REGEX, text) or
        findall(YTSHORTS_REGEX, text) or
        findall(VK_REGEX, text)
    )

def cleanup_files(*response_paths):
    for response_path in response_paths:
        if not response_path:
            continue
        try:
            os.remove(os.path.abspath(response_path))
        except Exception as e:
            logging.warning(f"Не удалось удалить {response_path}: {e}")

def convert_webm_to_mp4(input_file):
    output_file = f"{os.path.splitext(input_file)[0]}.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_file,
            "-c:v", "libx264", "-c:a", "aac", "-strict", "experimental", output_file
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_file
    except Exception as e:
        logging.error(f"Ошибка при конвертации webm в mp4: {e}")
        return None

async def notify_admin(text):
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        logging.error(f"Не удалось отправить ошибку админу: {e}")

@dp.message_handler(commands=['start', 'help'])
@dp.throttled(rate=2)
async def send_welcome(message: types.Message):
    user_lang = get_user_lang(message.from_user.locale)
    await message.reply(
        languages[user_lang]["help"],
        disable_notification=True
    )

@dp.message_handler(lambda message: is_supported_link(message.text))
@dp.throttled(rate=3)
async def handle_supported_links(message: types.Message):
    link = findall(r'\bhttps?://\S+', message.text)[0]

    wait_msg = await message.reply(
        "⏳ Пожалуйста, подождите!\nВаше видео/медиа загружается...",
        disable_notification=True
    )

    response = None
    converted_mp4 = None

    try:
        response = await yt_dlp(link)
        if not response or not os.path.exists(response):
            raise Exception(f"Ошибка: не удалось найти скачанный файл для ссылки {link}")

        if response.lower().endswith(".mp4"):
            with open(response, 'rb') as f:
                await message.reply_video(
                    f,
                    disable_notification=True
                )
        elif response.lower().endswith(".webm"):
            converted_mp4 = convert_webm_to_mp4(response)
            if converted_mp4 and os.path.exists(converted_mp4):
                with open(converted_mp4, 'rb') as f:
                    await message.reply_video(
                        f,
                        disable_notification=True
                    )
            else:
                raise Exception("Не удалось сконвертировать в mp4. mp4-версия недоступна для этого видео.")
        elif response.lower().endswith(".mp3"):
            with open(response, 'rb') as f:
                await message.reply_audio(
                    f,
                    title=link,
                    disable_notification=True
                )
        else:
            raise Exception("Файл не является видео mp4 и не может быть сконвертирован.")
        cleanup_files(response, converted_mp4)

    except Exception as e:
        logging.error(e)
        await message.reply("😔", disable_notification=True)
        await notify_admin(
            f"Ошибка: {e}\n\n"
            f"Ссылка: {link}\n"
            f"Пользователь: @{message.from_user.username} ({message.from_user.id})"
        )
        if response or converted_mp4:
            cleanup_files(response, converted_mp4)
    finally:
        try:
            await bot.delete_message(chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)
        except Exception as del_err:
            logging.warning(f"Не удалось удалить сообщение: {del_err}")

@dp.message_handler()
@dp.throttled(rate=3)
async def handle_invalid_links(message: types.Message):
    if message.chat.type == "private":
        await message.reply(
            "Я поддерживаю только ссылки на TikTok, VK и YouTube Shorts.\n"
            "Просто пришли ссылку на видео из этих сервисов.",
            disable_notification=True
        )
    # В группах и каналах никакой реакции

if __name__ == '__main__':
    if is_tool("yt-dlp"):
        logging.info("yt-dlp installed")
        executor.start_polling(dp, skip_updates=True)
    else:
        logging.error("yt-dlp not installed! Run: sudo apt install yt-dlp")

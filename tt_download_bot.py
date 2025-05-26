import logging
import os
from re import findall

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from tt_video import yt_dlp
from settings import languages, API_TOKEN

storage = MemoryStorage()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

def is_tool(name):
    from shutil import which
    return which(name) is not None

# Безопасное определение языка пользователя
def get_user_lang(locale):
    if locale and hasattr(locale, 'language'):
        return locale.language if locale.language in languages else "en"
    return "en"

TIKTOK_REGEX = r'https://(vm\.tiktok\.com|vt\.tiktok\.com|www\.tiktok\.com)/\S+'
YTSHORTS_REGEX = r'https://(youtube\.com/shorts/\S+|youtu\.be/\S+)'
INSTAGRAM_REGEX = r'https://(www\.)?instagram\.com/reel/\S+'
VK_REGEX = r'https://(www\.)?vk\.com/(video|clip)[\w\-/]+'

def is_supported_link(text: str) -> bool:
    return bool(
        findall(TIKTOK_REGEX, text) or
        findall(YTSHORTS_REGEX, text) or
        findall(INSTAGRAM_REGEX, text) or
        findall(VK_REGEX, text)
    )

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
    user_lang = get_user_lang(message.from_user.locale)
    link = findall(r'\bhttps?://\S+', message.text)[0]

    wait_msg = await message.reply(
        "Пожалуйста, подождите!\nВаше видео загружается...",
        disable_notification=True
    )

    try:
        response = await yt_dlp(link)
        if response.endswith(".mp3"):
            await message.reply_audio(
                open(response, 'rb'),
                title=link,
                disable_notification=True
            )
        else:
            await message.reply_video(
                open(response, 'rb'),
                disable_notification=True
            )
        os.remove(response)

    except Exception as e:
        logging.error(e)
        await message.reply(
            f"error: {e}",
            disable_notification=True
        )
        try:
            os.remove(response)
        except:
            pass
    finally:
        try:
            await bot.delete_message(chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)
        except Exception as del_err:
            logging.warning(f"Не удалось удалить сообщение: {del_err}")

@dp.message_handler()
@dp.throttled(rate=3)
async def handle_invalid_links(message: types.Message):
    if message.chat.type == 'private':
        await message.reply(
            "Неверная ссылка, пришлите правильную ссылку youtube.com/shorts/, Tik Tok, VK или Instagram Reals.",
            disable_notification=True
        )

if __name__ == '__main__':
    if is_tool("yt-dlp"):
        logging.info("yt-dlp installed")
        executor.start_polling(dp, skip_updates=True)
    else:
        logging.error("yt-dlp not installed! Run: sudo apt install yt-dlp")

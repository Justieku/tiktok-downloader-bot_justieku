import logging
import os
import glob
import uuid
from re import findall

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from gtts import gTTS
from pydub import AudioSegment
import speech_recognition as sr

from tt_video import yt_dlp
from settings import languages, API_TOKEN

storage = MemoryStorage()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

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

def cleanup_files(response_path):
    if not response_path:
        return

    try:
        os.remove(os.path.abspath(response_path))
    except Exception as e:
        logging.warning(f"Не удалось удалить {response_path}: {e}")

@dp.message_handler(commands=['start', 'help'])
@dp.throttled(rate=2)
async def send_welcome(message: types.Message):
    user_lang = get_user_lang(message.from_user.locale)
    await message.reply(
        languages[user_lang]["help"],
        disable_notification=True
    )

@dp.message_handler(commands=['tts'])
async def text_to_speech(message: types.Message):
    text = message.get_args()
    if not text:
        await message.reply("Пришлите текст после команды /tts", disable_notification=True)
        return

    tts = gTTS(text, lang='ru')
    filename = f"{uuid.uuid4()}.mp3"
    tts.save(filename)

    with open(filename, "rb") as f:
        await message.reply_voice(f, disable_notification=True)

    os.remove(filename)

def escape_markdown(text: str) -> str:
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + c if c in escape_chars else c for c in text])

@dp.message_handler(content_types=types.ContentType.VOICE)
async def voice_to_text(message: types.Message):
    file = await bot.get_file(message.voice.file_id)
    file_path = file.file_path
    file_name = f"{uuid.uuid4()}.ogg"
    wav_file = file_name.replace(".ogg", ".wav")

    try:
        await bot.download_file(file_path, file_name)
        sound = AudioSegment.from_ogg(file_name)
        sound.export(wav_file, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language="ru-RU")
                escaped_text = escape_markdown(text)
                await message.reply(
                    f"🗣 Распознанный текст:\n||{escaped_text}||",
                    parse_mode="MarkdownV2",
                    disable_notification=True,
                )
            except sr.UnknownValueError:
                await message.reply("Не удалось распознать голосовое сообщение, бред сумасшедшего", disable_notification=True)
    finally:
        # Удаляем оба файла в любом случае
        for f in (file_name, wav_file):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    logging.warning(f"Не удалось удалить {f}: {e}")

@dp.message_handler(lambda message: is_supported_link(message.text))
@dp.throttled(rate=3)
async def handle_supported_links(message: types.Message):
    user_lang = get_user_lang(message.from_user.locale)
    link = findall(r'\bhttps?://\S+', message.text)[0]

    wait_msg = await message.reply(
        "Пожалуйста, подождите!\nВаше видео загружается...",
        disable_notification=True
    )

    response = None

    try:
        response = await yt_dlp(link)
        if response.endswith(".mp3"):
            with open(response, 'rb') as f:
                await message.reply_audio(
                    f,
                    title=link,
                    disable_notification=True
                )
        else:
            with open(response, 'rb') as f:
                await message.reply_video(
                    f,
                    disable_notification=True
                )
        cleanup_files(response)

    except Exception as e:
        logging.error(e)
        await message.reply(
            f"error: {e}",
            disable_notification=True
        )
        if response:
            cleanup_files(response)
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
            "Неверная ссылка, пришлите правильную ссылку youtube.com/shorts/, TikTok или VK.",
            disable_notification=True
        )

if __name__ == '__main__':
    if is_tool("yt-dlp"):
        logging.info("yt-dlp installed")
        executor.start_polling(dp, skip_updates=True)
    else:
        logging.error("yt-dlp not installed! Run: sudo apt install yt-dlp")

import asyncio
import glob
import os
import platform
import re
from io import BytesIO
from PIL import Image

def divide_chunks(list, n):
    for i in range(0, len(list), n):
        yield list[i:i + n]

def convert_image(image, extention):  # "JPEG"
    byteImgIO = BytesIO()
    byteImg = Image.open(BytesIO(image)).convert("RGB")
    byteImg.save(byteImgIO, extention)
    byteImgIO.seek(0)
    return byteImgIO

def get_url_of_yt_dlp():
    download_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    if os_name is None or arch is None:
        print(f"Cant detect os({os_name}) or arch({arch})")
    else:
        print(os_name, arch)
        if os_name == "darwin":
            return f"{download_url}_macos"
        elif os_name == "windows":
            if arch in ["amd64", "x86_64"]:
                arch = ".exe"
            elif arch in ["i386", "i686"]:
                arch = "_x86.exe"
            else:
                return None
            return f"{download_url}{arch}"
        elif os_name == "linux":
            if arch in ["aarch64", "aarch64_be", "armv8b", "armv8l"]:
                arch = "_linux_aarch64"
            elif arch in ["amd64", "x86_64"]:
                arch = "_linux"
            elif arch == "armv7l":
                arch = "_linux_armv7l"
            else:
                return None
            return f"{download_url}{arch}"

def _find_best_video_file(filename_base):
    """
    Находит самый подходящий видеофайл (по возможности mp4), иначе webm, иначе любой из похожих.
    """
    candidates = glob.glob(f"{filename_base}*.mp4")
    if candidates:
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]

    candidates = glob.glob(f"{filename_base}*.webm")
    if candidates:
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]

    candidates = glob.glob(f"{filename_base}*")
    if candidates:
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]

    return None

# only video or music
async def yt_dlp(url):
    args = [
        'yt-dlp', url, "--max-filesize", "50M", "--max-downloads", "1", "--restrict-filenames",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
    except asyncio.exceptions.TimeoutError:
        try:
            proc.kill()
        except OSError:
            print("timeout no such process")
            pass
        raise Exception('Timeout: yt-dlp did not finish in 90 seconds')

    filename = None
    # Парсим вывод yt-dlp для имени файла
    for line in stdout.decode("utf-8").splitlines():
        print(line)
        match_dest = re.findall(r" Destination: (.*?)$", line)
        match_already = re.findall(r" (.*?) has already been downloaded$", line)
        if match_dest:
            filename = match_dest[0]
            break
        elif match_already:
            filename = match_already[0]
            break

    if not filename:
        err = stderr.decode("utf-8")
        raise Exception(f'Не удалось определить файл из вывода yt-dlp. stdout:\n{stdout.decode("utf-8")}\nstderr:\n{err}')

    filename_base = re.sub(r'\.f\d+(\.\w+)?$', '', filename)
    if os.path.exists(filename):
        return filename

    possible_mp4 = f"{filename_base}.mp4"
    if os.path.exists(possible_mp4):
        return possible_mp4

    possible_webm = f"{filename_base}.webm"
    if os.path.exists(possible_webm):
        return possible_webm

    best_file = _find_best_video_file(filename_base)
    if best_file:
        return best_file

    all_files = glob.glob("*")
    raise FileNotFoundError(
        f"{filename} not found. Tried: {possible_mp4}, {possible_webm}, and all matches for '{filename_base}*'.\n"
        f"Файлы в директории: {all_files}"
    )

# Новая функция для получения слайдов и аудио для TikTok Slides
async def tt_videos_or_images(url):
    # Пример реализации: 
    # Если это слайд-шоу (TikTok slides), используйте yt-dlp для скачивания изображений и аудио
    # Пример вызова:
    # yt-dlp -o "%(title)s/%(id)s.%(ext)s" --write-thumbnail --skip-download <url>
    temp_dir = str(uuid.uuid4())
    os.makedirs(temp_dir, exist_ok=True)
    args = [
        'yt-dlp', url, "-o", f"{temp_dir}/%(slide_number)s.%(ext)s",
        "--force-keyframes-at-cuts",
        "--write-thumbnail", "--write-info-json", "--write-all-thumbnails"
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
    except asyncio.exceptions.TimeoutError:
        try:
            proc.kill()
        except OSError:
            pass
        raise Exception('Timeout: yt-dlp did not finish in 90 seconds')

    # Соберём все изображения и аудио
    all_files = os.listdir(temp_dir)
    images = sorted([os.path.join(temp_dir, f) for f in all_files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    audio = None
    for f in all_files:
        if f.lower().endswith('.mp3') or f.lower().endswith('.m4a'):
            audio = os.path.join(temp_dir, f)
            break
    if images and audio:
        # Вернуть полный путь к изображениям и аудио
        return {'images': images, 'audio': audio}
    # Если не удалось, удалить временную папку
    for f in images:
        os.remove(f)
    if audio:
        os.remove(audio)
    os.rmdir(temp_dir)
    raise Exception('Не удалось получить слайды и аудио для данного TikTok')

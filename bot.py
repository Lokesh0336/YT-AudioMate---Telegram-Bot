import os
import logging
import subprocess
import random
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp
import dotenv

# Load environment variables from the .env file
dotenv.load_dotenv()

# --- Configuration ---
# Your bot token is now loaded from the .env file
BOT_TOKEN: str = os.environ.get("BOT_TOKEN")

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# --- Audio Compression Function ---
def compress_audio(input_path: str, output_path: str, bitrate: str = "64k") -> bool:
    ffmpeg_path = "/home/runner/.spotdl/ffmpeg"

    if not os.path.exists(ffmpeg_path):
        logger.error("FFmpeg binary not found at expected path.")
        return False

    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                input_path,
                "-b:a",
                bitrate,
                output_path,
            ],
            check=True,
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg compression failed: {e}")
        return False


# --- Quotes ---
start_quotes = [
    "Success usually comes to those who are too busy to be looking for it.",
    "Dream big. Start small. Act now.",
    "Every great achievement was once considered impossible.",
    "The secret of getting ahead is getting started.",
    "Stay positive. Work hard. Make it happen.",
]

finish_quotes = [
    "Keep going. Everything you need will come to you at the perfect time.",
    "The best view comes after the hardest climb.",
    "Turn your dreams into plans, and your plans into reality.",
    "Every step you take is a step toward your goal.",
    "Strive for progress, not perfection.",
]

# --- /start Command Handler ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"👋 Welcome <b>{user.mention_html()}</b>!\n\n"
        f"🎧 Just send me a YouTube video link and I’ll convert it to audio for you.\n\n"
        f"🤖 Created with ❤️ by <b>Lokesh.R</b>\n\n"
        f"Thank you for using this bot! 🚀\n\n"
        f"“{random.choice(start_quotes)}”"
    )
    logger.info(f"User {user.id} started the bot.")


# --- Audio Download Handler ---


async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    user_message: str = update.message.text or ""
    chat_id: int = update.message.chat_id
    user = update.effective_user

    waiting_quotes = [
        "Good things take time, just like this download. ☕",
        "Hang tight! We’re grabbing your audio. 🎵",
        "Almost there... your audio is on its way! 🚀",
        "Sit back and relax, the audio is brewing. 🎧",
        "Processing your link like a pro... 💼",
    ]

    logger.info(f"User {user.id} sent link: {user_message}")
    await update.message.reply_text(f"🔄 {random.choice(waiting_quotes)} — Lokesh.R")

    output_filename: str = f"audio_{chat_id}_{update.message.message_id}.mp3"
    final_file_path: Optional[str] = None

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_filename,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(user_message, download=True)
            if info_dict:
                downloaded_file_path = ydl.prepare_filename(info_dict)
                # yt-dlp may not rename the extension from webm/m4a to mp3 automatically after postprocessing
                if downloaded_file_path.endswith((".webm", ".m4a")):
                    downloaded_file_path = os.path.splitext(downloaded_file_path)[0] + ".mp3"

                final_file_path = downloaded_file_path

                if (
                    os.path.exists(downloaded_file_path)
                    and os.path.getsize(downloaded_file_path) > 49 * 1024 * 1024
                ):
                    compressed_path = f"compressed_{output_filename}"
                    if compress_audio(downloaded_file_path, compressed_path):
                        final_file_path = compressed_path
                        logger.info(f"Compressed large audio to: {final_file_path}")
                    else:
                        logger.warning("Compression failed or not needed; sending original file.")

                if final_file_path and os.path.exists(final_file_path):
                    file_size_mb: float = os.path.getsize(final_file_path) / (1024 * 1024)
                    if file_size_mb > 49:
                        await update.message.reply_text(
                            f"⚠️ The final audio file is too large to send via Telegram ({file_size_mb:.2f} MB).\n"
                            f"Try with a shorter video. — Lokesh.R\n\n"
                            f"“Great things are not done by impulse, but by a series of small things.”"
                        )
                        return

                    with open(final_file_path, "rb") as audio_file:
                        await update.message.reply_audio(
                            audio=audio_file,
                            title=info_dict.get("title", "YouTube Audio"),
                            performer=info_dict.get("uploader", "Unknown"),
                            caption=(
                                f"✅ Here's your audio: <b>{info_dict.get('title', 'your video')}</b>\n\n"
                                f"🤖 Created with ❤️ by Lokesh.R\n\n"
                                f"“{random.choice(finish_quotes)}”"
                            ),
                            parse_mode="HTML",
                        )
                    logger.info(f"Sent audio to user {user.id}.")
                else:
                    await update.message.reply_text(
                        "❌ Sorry, the audio file couldn't be found.\n"
                        "Please check the link and try again. — Lokesh.R"
                    )
                    logger.error("Final audio file not found.")
            else:
                await update.message.reply_text(
                    "⚠️ Sorry, the download failed. Please make sure the YouTube link is valid and try again.\n\n"
                    "🤖 Created with ❤️ by Lokesh.R"
                )
                logger.warning(f"yt-dlp extract_info failed for {user_message}")

    except yt_dlp.utils.DownloadError as e:
        await update.message.reply_text(
            f"❌ Error: {e}\nPlease try another link. — Lokesh.R\n\n"
            f"“Failure is not the opposite of success, it's part of success.”"
        )
        logger.error(f"DownloadError: {e}")

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Unexpected error occurred: {e}\n\n"
            "We’re sorry for the inconvenience. — Lokesh.R\n\n"
            "“Every challenge is an opportunity in disguise.”"
        )
        logger.exception(f"Unexpected error for {user_message}")

    finally:
        for path in [output_filename, f"compressed_{output_filename}", final_file_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Cleaned up file: {path}")
                except Exception as remove_e:
                    logger.warning(f"Failed to remove file {path}: {remove_e}")


# --- Main Function ---


def main() -> None:
    application: Application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))

    logger.info("Bot started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
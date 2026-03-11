#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Instagram Video Downloader Bot - FINAL VERSION (Stable for Render)

import os
import logging
import tempfile
import asyncio
import subprocess
from datetime import datetime, timedelta
import math

# Telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Downloader
import yt_dlp

# Video processing
from moviepy.editor import VideoFileClip

# Optional: Whisper (pake yang ringan)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️ Whisper not installed, /transcribe will be disabled")

# ============= KONFIGURASI =============
TOKEN = os.environ.get("BOT_TOKEN", "ISI_TOKEN_BOT_DARI_BOTFATHER")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILE_SIZE_SPLIT = 45 * 1024 * 1024  # 45 MB
COOKIE_FILE = 'cookies.txt'
TEMP_DIR = tempfile.gettempdir()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load Whisper model (if available)
if WHISPER_AVAILABLE:
    model_name = os.environ.get("WHISPER_MODEL", "tiny")
    print(f"Loading Whisper model: {model_name}...")
    whisper_model = whisper.load_model(model_name)
    print("✅ Whisper model loaded!")
else:
    whisper_model = None

# ============= FUNGSI DOWNLOAD =============
async def download_instagram(url):
    """Download video Instagram tanpa watermark"""
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{TEMP_DIR}/instagram_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    # Tambah cookie kalo ada
    if os.path.exists(COOKIE_FILE):
        ydl_opts['cookiefile'] = COOKIE_FILE
        logger.info("✅ Using cookies")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Pastikan .mp4
            if not filename.endswith('.mp4'):
                filename = filename.replace(info.get('ext', ''), 'mp4')
            
            return {
                'success': True,
                'filepath': filename,
                'title': str(info.get('title', 'Instagram Video')),
                'duration': int(info.get('duration', 0)),
                'uploader': str(info.get('uploader', 'Unknown')),
                'filesize': os.path.getsize(filename) if os.path.exists(filename) else 0
            }
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return {'success': False, 'error': str(e)}

# ============= SPLIT VIDEO =============
async def split_video(filepath):
    """Split video kalo >45MB"""
    file_size = os.path.getsize(filepath)
    if file_size <= MAX_FILE_SIZE_SPLIT:
        return [filepath]
    
    logger.info(f"Splitting {file_size} bytes video...")
    try:
        video = VideoFileClip(filepath)
        duration = video.duration
        bitrate = file_size / duration
        part_duration = int(MAX_FILE_SIZE_SPLIT / bitrate) - 5
        if part_duration < 10:
            part_duration = 10
        
        num_parts = math.ceil(duration / part_duration)
        video.close()
        
        part_files = []
        for i in range(num_parts):
            start_time = i * part_duration
            output_path = filepath.replace('.mp4', f'_part{i+1}.mp4')
            cmd = [
                'ffmpeg', '-i', filepath,
                '-ss', str(start_time),
                '-t', str(part_duration),
                '-c', 'copy', '-y', output_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=60)
            if os.path.exists(output_path):
                part_files.append(output_path)
        return part_files
    except Exception as e:
        logger.error(f"Split error: {e}")
        return [filepath]

# ============= EXTRACT AUDIO =============
async def extract_audio(video_path):
    """Ekstrak audio MP3"""
    try:
        audio_path = video_path.replace('.mp4', '.mp3')
        video = VideoFileClip(video_path)
        audio = video.audio
        audio.write_audiofile(audio_path, logger=None)
        video.close()
        return audio_path
    except Exception as e:
        logger.error(f"Audio extraction error: {str(e)}")
        return None

# ============= TRANSCRIBE =============
async def transcribe_media(filepath):
    """Transkrip pake Whisper"""
    if not WHISPER_AVAILABLE or whisper_model is None:
        return None, "Whisper not available"
    
    try:
        audio_path = filepath
        if filepath.endswith('.mp4'):
            audio_path = filepath.replace('.mp4', '.wav')
            video = VideoFileClip(filepath)
            audio = video.audio
            audio.write_audiofile(audio_path, logger=None)
            video.close()
        
        result = whisper_model.transcribe(audio_path, language='id')
        
        if audio_path != filepath and os.path.exists(audio_path):
            os.remove(audio_path)
        
        return result['text'], None
    except Exception as e:
        logger.error(f"Transcribe error: {e}")
        return None, str(e)

# ============= TELEGRAM HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    msg = (
        "🎥 *Instagram Video Downloader*\n\n"
        "Kirim link Instagram, bot akan download videonya.\n\n"
        "Commands:\n"
        "/start - Pesan ini\n"
        "/transcribe - Transkrip video terakhir\n"
        "/audio - Ambil audio MP3\n"
        "/help - Bantuan"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /help"""
    msg = (
        "📌 *Cara Penggunaan:*\n"
        "1. Kirim link Instagram (reels/post/igtv)\n"
        "2. Tunggu proses download\n"
        "3. Video akan dikirim\n\n"
        "Fitur:\n"
        "- /audio: ambil MP3 dari video\n"
        "- /transcribe: transkrip ke teks\n\n"
        "⚠️ Maks file: 50MB"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /audio"""
    if 'last_video' not in context.user_data:
        await update.message.reply_text("❌ Kirim link Instagram dulu!")
        return
    
    video_path = context.user_data['last_video']
    if not os.path.exists(video_path):
        await update.message.reply_text("❌ File video sudah tidak ada")
        return
    
    status = await update.message.reply_text("🎵 Mengekstrak audio...")
    audio_path = await extract_audio(video_path)
    
    if not audio_path:
        await status.edit_text("❌ Gagal ekstrak audio")
        return
    
    try:
        with open(audio_path, 'rb') as audio:
            await update.message.reply_audio(audio=audio)
        os.remove(audio_path)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Gagal kirim audio: {str(e)}")

async def transcribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /transcribe"""
    if not WHISPER_AVAILABLE:
        await update.message.reply_text("❌ Fitur transcribe tidak tersedia")
        return
    
    if 'last_video' not in context.user_data:
        await update.message.reply_text("❌ Kirim link Instagram dulu!")
        return
    
    video_path = context.user_data['last_video']
    if not os.path.exists(video_path):
        await update.message.reply_text("❌ File video sudah tidak ada")
        return
    
    status = await update.message.reply_text("📝 Mentranskrip... (bisa 1-2 menit)")
    text, error = await transcribe_media(video_path)
    
    if error:
        await status.edit_text(f"❌ Gagal: {error}")
        return
    
    if len(text) > 4000:
        text = text[:4000] + "...\n\n(teks dipotong)"
    
    await status.edit_text(f"📝 *Hasil Transkrip:*\n\n{text}", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk link Instagram"""
    url = update.message.text.strip()
    
    if not ('instagram.com' in url or 'instagr.am' in url):
        await update.message.reply_text("❌ Kirim link Instagram yang valid!")
        return
    
    status = await update.message.reply_text("⏬ Downloading...")
    result = await download_instagram(url)
    
    if not result['success']:
        await status.edit_text(f"❌ Gagal: {result['error']}")
        return
    
    file_size = os.path.getsize(result['filepath'])
    if file_size > MAX_FILE_SIZE:
        await status.edit_text("❌ File >50MB, tidak bisa dikirim")
        os.remove(result['filepath'])
        return
    
    context.user_data['last_video'] = result['filepath']
    await status.edit_text("📤 Mengirim video...")
    
    try:
        caption = f"✅ *{result['title'][:50]}*"
        if result['duration']:
            minutes = result['duration'] // 60
            seconds = result['duration'] % 60
            caption += f"\n⏱️ {minutes}:{seconds:02d}"
        
        with open(result['filepath'], 'rb') as video:
            await update.message.reply_video(
                video=video,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
        
        os.remove(result['filepath'])
        await status.delete()
        
    except Exception as e:
        await status.edit_text(f"❌ Gagal kirim: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ Terjadi error, coba lagi nanti")

# ============= MAIN =============
def main():
    """Main function - CARA TERBARU DAN STABIL"""
    print("🤖 Instagram Bot starting...")
    
    # Create application - UPDATER TIDAK DIGUNAKAN LANGSUNG
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("transcribe", transcribe))
    app.add_handler(CommandHandler("audio", audio_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    # Start bot - INI YANG BENER
    print("✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Instagram Bot - Minimal Version for Azure

import os
import logging
import tempfile
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# ============= KONFIGURASI =============
TOKEN = os.environ.get("BOT_TOKEN", "ISI_TOKEN_BOT_DARI_BOTFATHER")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
COOKIE_FILE = 'cookies.txt'

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= FUNGSI DOWNLOAD =============
async def download_instagram(url):
    """Download video dari Instagram"""
    
    # Cek cookie
    use_cookie = os.path.exists(COOKIE_FILE)
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{tempfile.gettempdir()}/instagram_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    if use_cookie:
        ydl_opts['cookiefile'] = COOKIE_FILE
        logger.info("✅ Menggunakan cookie")
    
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
                'duration': int(info.get('duration', 0))
            }
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return {'success': False, 'error': str(e)}

# ============= HANDLER TELEGRAM =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    await update.message.reply_text(
        "🎥 *Instagram Video Downloader*\n\n"
        "Kirim link Instagram, bot akan download videonya.\n\n"
        "Commands:\n"
        "/start - Pesan ini\n"
        "/help - Bantuan",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /help"""
    await update.message.reply_text(
        "📌 *Cara Penggunaan:*\n"
        "1. Kirim link Instagram (reels/post/igtv)\n"
        "2. Tunggu proses download\n"
        "3. Video akan dikirim\n\n"
        "⚠️ Maks file: 50MB",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk link Instagram"""
    url = update.message.text.strip()
    
    if not ('instagram.com' in url or 'instagr.am' in url):
        await update.message.reply_text("❌ Kirim link Instagram yang valid!")
        return
    
    status_msg = await update.message.reply_text("⏬ *Downloading...*", parse_mode='Markdown')
    
    result = await download_instagram(url)
    
    if not result['success']:
        await status_msg.edit_text(f"❌ Gagal: {result['error']}")
        return
    
    # Cek ukuran
    file_size = os.path.getsize(result['filepath'])
    if file_size > MAX_FILE_SIZE:
        await status_msg.edit_text("❌ File terlalu besar (max 50MB)")
        os.remove(result['filepath'])
        return
    
    await status_msg.edit_text("📤 *Mengirim video...*", parse_mode='Markdown')
    
    try:
        with open(result['filepath'], 'rb') as video:
            caption = f"✅ *Download sukses!*\n"
            caption += f"📹 *{result['title'][:50]}*"
            
            await update.message.reply_video(
                video=video,
                caption=caption,
                parse_mode='Markdown'
            )
        
        os.remove(result['filepath'])
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Gagal kirim: {str(e)}")
        if os.path.exists(result['filepath']):
            os.remove(result['filepath'])

# ============= MAIN =============
def main():
    """Main function"""
    print("🤖 Instagram Bot starting...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot is running!")
    app.run_polling()

if __name__ == '__main__':
    main()

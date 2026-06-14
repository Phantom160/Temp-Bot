import requests
import time
import asyncio
import json
import random
import string
import re
from html import unescape
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIG ====================
BOT_TOKEN = "8992928804:AAEZc_I8Fcxgx98JqgmRGb-EpwZbGJVFwJw"

# Multiple Admins - Add as many as you want
ADMIN_IDS = [
    7641052727,  # Admin 1 (original)
    1361987726,
8780194092,  # Admin 2 (new)
    # Add more here
]

# Store temp emails
temp_emails = {}

# ==================== FUNCTIONS ====================
def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_temp_email():
    """Create temp email using Mail.tm"""
    try:
        url = "https://api.mail.tm/domains"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            domains = resp.json()
            if domains and domains.get('hydra:member'):
                domain = domains['hydra:member'][0]['domain']
                
                email = f"{generate_random_string(12)}@{domain}"
                password = f"Temp@{generate_random_string(8)}"
                
                create_url = "https://api.mail.tm/accounts"
                payload = {"address": email, "password": password}
                resp = requests.post(create_url, json=payload, timeout=10)
                
                if resp.status_code == 201:
                    login_url = "https://api.mail.tm/token"
                    login_payload = {"address": email, "password": password}
                    resp = requests.post(login_url, json=login_payload, timeout=10)
                    
                    if resp.status_code == 200:
                        token = resp.json().get('token')
                        return email, token, password
    except Exception as e:
        print(f"Mail.tm error: {e}")
    
    return None, None, None

def check_messages(token):
    try:
        url = "https://api.mail.tm/messages"
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('hydra:member', [])
    except Exception as e:
        print(f"Check messages error: {e}")
    return []

def get_message(token, msg_id):
    try:
        url = f"https://api.mail.tm/messages/{msg_id}"
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Get message error: {e}")
    return None

def clean_text(text):
    if not text or not isinstance(text, str):
        return ""
    
    text = unescape(text)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    if len(text) > 500:
        text = text[:500] + "..."
    
    return text

def extract_otp(text):
    if not text:
        return None
    match = re.search(r'\b\d{6}\b', text)
    if match:
        return match.group()
    return None

async def monitor_email(email, token, bot, chat_id):
    seen_ids = set()
    
    while True:
        try:
            messages = check_messages(token)
            
            if messages:
                for msg in messages:
                    msg_id = msg.get('id')
                    if msg_id and msg_id not in seen_ids:
                        content = get_message(token, msg_id)
                        if content:
                            seen_ids.add(msg_id)
                            
                            subject = content.get('subject', 'No Subject')
                            from_addr = content.get('from', {})
                            if isinstance(from_addr, dict):
                                from_addr = from_addr.get('address', 'Unknown')
                            
                            body = content.get('html', [{}])[0] if content.get('html') else content.get('text', '')
                            if isinstance(body, dict):
                                body = body.get('body', '')
                            
                            body = clean_text(body)
                            otp = extract_otp(body) or extract_otp(subject)
                            
                            if otp:
                                msg_text = f"🔐 *OTP Found!*\n\n`{otp}`"
                            else:
                                msg_text = f"📧 *New Email*\n\n👤 From: {from_addr}\n📌 Subject: {subject}\n\n📝 {body[:200]}"
                            
                            try:
                                await bot.send_message(chat_id=chat_id, text=msg_text, parse_mode='Markdown')
                            except:
                                await bot.send_message(chat_id=chat_id, text=msg_text)
            
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Monitor error: {e}")
            await asyncio.sleep(10)

# ==================== BOT COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    text = """🤖 *Temp Mail Bot*

Commands:
/create - Create temp email
/list - List all emails
/delete <id> - Delete email
/delall - Delete all
/stats - Stats
/admins - List all admins"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def create_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    msg = await update.message.reply_text("⏳ Creating temp email...")
    
    email, token, password = create_temp_email()
    
    if email:
        email_id = generate_random_string(8)
        temp_emails[email_id] = {
            "email": email,
            "token": token,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": user_id
        }
        
        asyncio.create_task(monitor_email(email, token, context.bot, user_id))
        
        text = f"✅ *Temp Email Created!*\n\n📧 `{email}`\n🆔 `{email_id}`"
        await msg.edit_text(text, parse_mode='Markdown')
    else:
        await msg.edit_text("❌ Failed! Try again.")

async def list_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not temp_emails:
        await update.message.reply_text("📭 No emails. Use /create")
        return
    
    text = "*📧 Active Emails:*\n\n"
    for email_id, data in temp_emails.items():
        text += f"🆔 `{email_id}` → `{data['email']}`\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def delete_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    
    email_id = args[0]
    
    if email_id in temp_emails:
        del temp_emails[email_id]
        await update.message.reply_text(f"✅ Deleted `{email_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Not found")

async def delete_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    temp_emails.clear()
    await update.message.reply_text("✅ All emails deleted!")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    total = len(temp_emails)
    await update.message.reply_text(f"📊 *Stats*\n\nTotal Emails: `{total}`", parse_mode='Markdown')

async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    text = "*👑 Admins:*\n\n"
    for admin_id in ADMIN_IDS:
        text += f"• `{admin_id}`\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== MAIN ====================
def main():
    print("=" * 40)
    print("🤖 Temp Mail Bot Starting...")
    print("=" * 40)
    print(f"✅ Admins: {ADMIN_IDS}")
    print("=" * 40)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create_email))
    app.add_handler(CommandHandler("list", list_emails))
    app.add_handler(CommandHandler("delete", delete_email))
    app.add_handler(CommandHandler("delall", delete_all))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("admins", admins_cmd))
    
    print("✅ Bot running!")
    app.run_polling()

if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call(['pip', 'install', 'requests'])
    
    try:
        import telegram
    except ImportError:
        import subprocess
        subprocess.check_call(['pip', 'install', 'python-telegram-bot==20.7'])
    
    main()
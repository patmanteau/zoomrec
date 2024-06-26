import logging
import os
import signal
import subprocess
import atexit
import yaml
from datetime import datetime

# Get vars
BASE_PATH = os.getenv('HOME')
CSV_PATH = os.path.join(BASE_PATH, "meetings.csv")
EMAIL_TYPE_PATH = os.path.join(BASE_PATH, "email_types.yaml")

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

EMAIL_TYPE_PATH = os.path.join(BASE_PATH, "email_types.yaml")
IMAP_SERVER = os.getenv('IMAP_SERVER')
IMAP_PORT = os.getenv('IMAP_PORT')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD  = os.getenv('EMAIL_PASSWORD')

# Get the current date and time
now = datetime.now()

# Format the date and time in the desired format
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

# Create the log file name with the timestamp
LOG_DIR = os.path.join(BASE_PATH, os.getenv('LOG_SUBDIR'))
log_file = os.path.join(LOG_DIR, "{}.log".format(timestamp))

# Configure the logging
logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def start_telegram_bot():
    if not TELEGRAM_BOT_TOKEN:
        logging.info("Telegram token is missing. No Telegram bot will be started!")
        return
    
    bot_log_file = open(f"{log_file}.telegram_bot", "w")
    
    command = f"python3 telegram_bot.py {CSV_PATH} {TELEGRAM_BOT_TOKEN}"
    telegram_bot = subprocess.Popen(
        command, stdout=bot_log_file, stderr=bot_log_file, shell=True, preexec_fn=os.setsid, universal_newlines=True, bufsize=1)

    atexit.register(os.killpg, os.getpgid(
        telegram_bot.pid), signal.SIGQUIT)  
    
    logging.info("Telegram bot started!")
    
def start_imap_bot():
    if not (EMAIL_PASSWORD and IMAP_SERVER and IMAP_PORT and EMAIL_ADDRESS):
        logging.info("IMAP details missing. No IMAP email bot will be started!")
        return
    
    bot_log_file = open(f"{log_file}.imap_bot", "w")
    
    command = f"python3 imap_bot.py {CSV_PATH} {EMAIL_TYPE_PATH} {IMAP_SERVER} {IMAP_PORT} {EMAIL_ADDRESS} {EMAIL_PASSWORD} {TELEGRAM_BOT_TOKEN}"
    imap_bot = subprocess.Popen(
        command, stdout=bot_log_file, stderr=bot_log_file, shell=True, preexec_fn=os.setsid, universal_newlines=True, bufsize=1)

    atexit.register(os.killpg, os.getpgid(
        imap_bot.pid), signal.SIGQUIT)
    
    logging.info("IMAP email bot started!")

def start_api_server():
    # Define the Gunicorn command   
    gunicorn_command = [
        'gunicorn',
        '-c',
        'gunicorn_conf.py',  # gunicorn config
        'zoomrec_server_app:app'
    ]

    # Start Gunicorn using the subprocess module
    subprocess.call(gunicorn_command)

def main():

    # start bots
    start_telegram_bot()
    start_imap_bot()

    # start flask API app / blocking
    start_api_server()
    

if __name__ == '__main__':
    main()

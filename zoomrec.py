import csv
import logging
import os
import psutil 
import pyautogui  # later zoom versions do not start anymore when pyautogui is imported, Zoom  5.13.0 (599) still works
import random
import schedule
import signal
import subprocess
import threading
import time
import datetime
import atexit
import requests
from datetime import datetime, timedelta
from telegram_bot import start_bot
from events import expand_days, WEEKDAYS, DATE_FORMAT

global ONGOING_MEETING
global VIDEO_PANEL_HIDED
global TELEGRAM_BOT_TOKEN
global TELEGRAM_RETRIES
global TELEGRAM_CHAT_ID

UC_CONNECTED_NOPOPUPS = 1

# Turn DEBUG on:
#   - screenshot on error
#   - record joining
#   - do not exit container on error
DEBUG = True if os.getenv('DEBUG') == 'True' else False

# Disable failsafe
pyautogui.FAILSAFE = False

# Get vars
BASE_PATH = os.getenv('HOME')
CSV_PATH = os.path.join(BASE_PATH, "meetings.csv")
IMG_PATH = os.path.join(BASE_PATH, "img")
REC_PATH = os.path.join(BASE_PATH, "recordings")
AUDIO_PATH = os.path.join(BASE_PATH, "audio")
DEBUG_PATH = os.path.join(REC_PATH, "screenshots")

FFMPEG_INPUT_PARAMS = os.getenv('FFMPEG_INPUT_PARAMS')
FFMPEG_OUTPUT_PARAMS = os.getenv('FFMPEG_OUTPUT_PARAMS')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_RETRIES = 5

YAML_PATH = os.path.join(BASE_PATH, "email_types.yaml")
IMAP_SERVER = os.getenv('IMAP_SERVER')
IMAP_PORT = os.getenv('IMAP_PORT')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD  = os.getenv('EMAIL_PASSWORD')

DISPLAY_NAME = os.getenv('DISPLAY_NAME')
if DISPLAY_NAME is None or  len(DISPLAY_NAME) < 3:
    NAME_LIST = [
        'iPhone',
        'iPad',
        'Macbook',
        'Desktop',
        'Huawei',
        'Mobile',
        'PC',
        'Windows',
        'Home',
        'MyPC',
        'Computer',
        'Android'
    ]
    DISPLAY_NAME = random.choice(NAME_LIST)

TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"
CSV_DELIMITER = ';'

ONGOING_MEETING = False
VIDEO_PANEL_HIDED = False

# Get the current date and time
now = datetime.now()

# Format the date and time in the desired format
timestamp = now.strftime("%d-%m-%Y %H:%M")

# Create the log file name with the timestamp
log_file = DEBUG_PATH + "/{}.log".format(timestamp)

# Configure the logging
logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)


class BackgroundThread:

    def __init__(self, interval=10):
        # Sleep interval between
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        global ONGOING_MEETING
        ONGOING_MEETING = True

        logging.debug("Check continuously if meeting has ended..")

        while ONGOING_MEETING:

            # Check if recording
            if (pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'meeting_is_being_recorded.png'), confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("This meeting is being recorded..")
                try:
                    x, y = pyautogui.locateCenterOnScreen(os.path.join(
                        IMG_PATH, 'got_it.png'), confidence=0.9)
                    pyautogui.click(x, y)
                    logging.info("Accepted recording..")
                except TypeError:
                    logging.error("Could not accept recording!")

            # Check if ended
            if (pyautogui.locateOnScreen(os.path.join(IMG_PATH, 'meeting_ended_by_host_1.png'),
                                         confidence=0.9) is not None or pyautogui.locateOnScreen(
                os.path.join(IMG_PATH, 'meeting_ended_by_host_2.png'), confidence=0.9) is not None):
                ONGOING_MEETING = False
                logging.info("Meeting ended by host..")
            time.sleep(self.interval)


class HideViewOptionsThread:

    def __init__(self, description, interval=10):
        # Sleep interval between
        self.description = description
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        global VIDEO_PANEL_HIDED
        logging.info("Checking continuously if screensharing, polls or chats need hiding..")
        while ONGOING_MEETING:
            # Check if host is sharing poll results
            if (pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'host_is_sharing_poll_results.png'),
                                               confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("Host is sharing poll results..")
                try:
                    x, y = pyautogui.locateCenterOnScreen(os.path.join(
                        IMG_PATH, 'host_is_sharing_poll_results.png'), confidence=0.9)
                    pyautogui.click(x, y)
                    try:
                        x, y = pyautogui.locateCenterOnScreen(os.path.join(
                            IMG_PATH, 'exit.png'), confidence=0.9)
                        pyautogui.click(x, y)
                        logging.info("Closed poll results window..")
                    except TypeError:
                        logging.error("Could not exit poll results window!")
                        if DEBUG:
                            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                                TIME_FORMAT) + "-" + self.description) + "_close_poll_results_error.png")
                except TypeError:
                    logging.error("Could not find poll results window anymore!")
                    if DEBUG:
                        pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                            TIME_FORMAT) + "-" + self.description) + "_find_poll_results_error.png")

            # Check if view options available
            if pyautogui.locateOnScreen(os.path.join(IMG_PATH, 'view_options.png'), confidence=0.9) is not None:
                if not VIDEO_PANEL_HIDED:
                    logging.info("Screensharing active..")
                    try:
                        x, y = pyautogui.locateCenterOnScreen(os.path.join(
                            IMG_PATH, 'view_options.png'), confidence=0.9)
                        pyautogui.click(x, y)
                        time.sleep(1)
                        # Hide video panel
                        if pyautogui.locateOnScreen(os.path.join(IMG_PATH, 'show_video_panel.png'),
                                                    confidence=0.9) is not None:
                            # Leave 'Show video panel' and move mouse from screen
                            pyautogui.moveTo(0, 100)
                            pyautogui.click(0, 100)
                            VIDEO_PANEL_HIDED = True
                        else:
                            try:
                                x, y = pyautogui.locateCenterOnScreen(os.path.join(
                                    IMG_PATH, 'hide_video_panel.png'), confidence=0.9)
                                pyautogui.click(x, y)
                                # Move mouse from screen
                                pyautogui.moveTo(0, 100)
                                VIDEO_PANEL_HIDED = True
                            except TypeError:
                                logging.error("Could not hide video panel!")
                    except TypeError:
                        logging.error("Could not find view options!")

            # Check if meeting chat is on screen
            if pyautogui.locateOnScreen(os.path.join(IMG_PATH, 'meeting_chat.png'), confidence=0.9) is not None:
                logging.info("Meeting chat popup window detected...")
                # try to close window
                x, y = pyautogui.locateCenterOnScreen(os.path.join(
                            IMG_PATH, 'exit.png'), confidence=0.9)
                pyautogui.click(x, y)
                time.sleep(1)
                if pyautogui.locateOnScreen(os.path.join(IMG_PATH, 'meeting_chat.png'), confidence=0.9):
                    logging.info("Failed to close meeting chat popup window...")
                else:
                    logging.info("Successfully close meeting chat popup window...")
            else:
                VIDEO_PANEL_HIDED = False

            time.sleep(self.interval)

def send_telegram_message(text):
    global TELEGRAM_BOT_TOKEN
    global TELEGRAM_CHAT_ID
    global TELEGRAM_RETRIES
	
    if TELEGRAM_BOT_TOKEN is None:
        logging.error("Telegram token is missing. No Telegram messages will be send!")
        return
    
    if TELEGRAM_CHAT_ID is None:
        logging.error("Telegram chat_id is missing. No Telegram messages will be send!")
        return
        
    if len(TELEGRAM_BOT_TOKEN) < 3 or len(TELEGRAM_CHAT_ID) < 3:
        logging.error("Telegram token or chat_id missing. No Telegram messages will be send!")
        return

    url_req = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage" + "?chat_id=" + TELEGRAM_CHAT_ID + "&text=" + text 
    tries = 0
    done = False
    while not done:
        results = requests.get(url_req)
        results = results.json()
        done = 'ok' in results and results['ok']
        tries+=1
        if not done and tries < TELEGRAM_RETRIES:
            logging.error("Sending Telegram message failed, retring in 5 seconds...")
            time.sleep(5)
        if not done and tries >= TELEGRAM_RETRIES:
            logging.error("Sending Telegram message failed {} times, please check your credentials!".format(tries))
            done = True
       
def check_connecting(zoom_pid, start_date, duration):
    # Check if connecting
    check_periods = 0
    connecting = False
    # Check if connecting
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'connecting.png'), confidence=0.9) is not None:
        connecting = True
        logging.info("Connecting..")

    # Wait while connecting
    # Exit when meeting ends after time
    while connecting:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom_pid), signal.SIGQUIT)
            return

        if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'connecting.png'), confidence=0.9) is None:
            logging.info("Maybe not connecting anymore..")
            check_periods += 1
            if check_periods >= 2:
                connecting = False
                logging.info("Not connecting anymore..")
                return
        time.sleep(2)


def join_meeting_id(meet_id):
    logging.info("Join a meeting by ID..")
    found_join_meeting = False
    try:
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'join_meeting.png'), minSearchTime=2, confidence=0.9)
        pyautogui.click(x, y)
        found_join_meeting = True
    except TypeError:
        pass

    if not found_join_meeting:
        logging.error("Could not find 'Join Meeting' on screen!")
        return False

    time.sleep(2)

    # Insert meeting id
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.write(meet_id, interval=0.1)

    # Insert name
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.write(DISPLAY_NAME, interval=0.1)

    # Configure
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('space')

    time.sleep(2)

    return check_error()


def join_meeting_url():
    logging.info("Join a meeting by URL..")

    # Insert name
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.write(DISPLAY_NAME, interval=0.1)

    # Configure
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('space')

    time.sleep(2)

    return check_error()
    

def check_error():
    # Sometimes invalid id error is displayed
    if pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'invalid_meeting_id.png'), confidence=0.9) is not None:
        logging.error("Maybe a invalid meeting id was inserted..")
        left = False
        try:
            x, y = pyautogui.locateCenterOnScreen(
                os.path.join(IMG_PATH, 'leave.png'), confidence=0.9)
            pyautogui.click(x, y)
            left = True
        except TypeError:
            pass
            # Valid id

        if left:
            if pyautogui.locateCenterOnScreen(os.path.join(
                    IMG_PATH, 'join_meeting.png'), confidence=0.9) is not None:
                logging.error("Invalid meeting id!")
                return False
        else:
            return True

    if pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'authorized_attendees_only.png'), confidence=0.9) is not None:
        logging.error("This meeting is for authorized attendees only!")
        return False

    return True


def find_process_id_by_name(process_name):
    list_of_process_objects = []
    # Iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['pid', 'name'])
            # Check if process name contains the given name string.
            if process_name.lower() in pinfo['name'].lower():
                list_of_process_objects.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return list_of_process_objects


def show_toolbars():
    # Mouse move to show toolbar
    width, height = pyautogui.size()
    y = (height / 2)
    pyautogui.moveTo(0, y, duration=0.5)
    pyautogui.moveTo(width - 1, y, duration=0.5)


def join_audio(description):
    audio_joined = False
    try:
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'join_with_computer_audio.png'), confidence=0.9)
        logging.info("Join with computer audio..")
        pyautogui.click(x, y)
        audio_joined = True
        return True
    except TypeError:
        logging.error("Could not join with computer audio!")
        if DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_join_with_computer_audio_error.png")
    time.sleep(1)
    if not audio_joined:
        try:
            show_toolbars()
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'join_audio.png'), confidence=0.9)
            pyautogui.click(x, y)
            join_audio(description)
        except TypeError:
            logging.error("Could not join audio!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(

                    TIME_FORMAT) + "-" + description) + "_join_audio_error.png")
            return False


def unmute(description):
    try:
        show_toolbars()
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'unmute.png'), confidence=0.9)
        pyautogui.click(x, y)
        return True
    except TypeError:
        logging.error("Could not unmute!")
        if DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(TIME_FORMAT) + "-" + description) + "_unmute_error.png")
        return False


def mute(description):
    try:
        show_toolbars()
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'mute.png'), confidence=0.9)
        pyautogui.click(x, y)
        return True
    except TypeError:
        logging.error("Could not mute!")
        if DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(TIME_FORMAT) + "-" + description) + "_mute_error.png")
        return False


def join(meet_id, meet_pw, duration, description):
    global VIDEO_PANEL_HIDED
    ffmpeg_debug = None

    logging.info("Join meeting: " + description)

    if DEBUG:
        # Start recording
        width, height = pyautogui.size()
        resolution = str(width) + 'x' + str(height)
        disp = os.getenv('DISPLAY')

        logging.debug("Start recording joining process...")

        filename = os.path.join( 
            REC_PATH, time.strftime(TIME_FORMAT)) + "-" + description + "-JOIN.mkv"

        command = "ffmpeg -nostats -loglevel error -f pulse -ac 2 -i 1 -f x11grab -r 30 -s " + \
            resolution + " " + FFMPEG_INPUT_PARAMS + " -i " + disp + " " + FFMPEG_OUTPUT_PARAMS + \
            " -threads 0 -async 1 -vsync 1 \"" + filename + "\""

        logging.info("Recording command:" + command)

        ffmpeg_debug = subprocess.Popen(
            command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        atexit.register(os.killpg, os.getpgid(
            ffmpeg_debug.pid), signal.SIGQUIT)

    # Exit Zoom if running
    exit_process_by_name("zoom")

    join_by_url = meet_id.startswith('https://') or meet_id.startswith('http://')

    if not join_by_url:
        # Start Zoom
        zoom = subprocess.Popen("zoom", stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
        img_name = 'join_meeting.png'
    else:
        logging.info("Starting zoom with url")
        zoom = subprocess.Popen(f'zoom --url="{meet_id}"', stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
        img_name = 'join.png'
    
    # Wait while zoom process is there
    list_of_process_ids = find_process_id_by_name('zoom')
    while len(list_of_process_ids) <= 0:
        logging.info("No Running Zoom Process found!")
        list_of_process_ids = find_process_id_by_name('zoom')
        time.sleep(1)

    # Wait for zoom is started
    loop = True
    useCase = 0 # standard use case
    while (loop):
        if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, img_name), confidence=0.9):
            loop = False
        else:
           if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'leave_red.png'), confidence=0.9):
               loop = False
               useCase = UC_CONNECTED_NOPOPUPS

        logging.info("Zoom not ready yet!")
        time.sleep(1)

    logging.info("Zoom started!")
    start_date = datetime.now()

    if not join_by_url:
        joined = join_meeting_id(meet_id)
    else:
        time.sleep(2)
        if useCase == UC_CONNECTED_NOPOPUPS:
            joined = True # there is popup to input display name or anything
        else:
            joined = join_meeting_url()

    if not joined:
        send_telegram_message("Failed to join meeting {}!".format(description))
        logging.error("Failed to join meeting!")
        os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
        if DEBUG and ffmpeg_debug is not None:
            # closing ffmpeg
            os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
            atexit.unregister(os.killpg)
        return

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    if not join_by_url:
        pyautogui.write(meet_pw, interval=0.2)
        pyautogui.press('tab')
        pyautogui.press('space')

    # Joined meeting
    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    # Check if meeting is started by host
    check_periods = 0
    meeting_started = True

    time.sleep(2)

    # Check if waiting for host
    if pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'wait_for_host.png'), confidence=0.9, minSearchTime=3) is not None:
        meeting_started = False
        logging.info("Please wait for the host to start this meeting.")

    # Wait for the host to start this meeting
    # Exit when meeting ends after time
    while not meeting_started:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
            if DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
                atexit.unregister(os.killpg)
            return

        if pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'wait_for_host.png'), confidence=0.9) is None:
            logging.info("Maybe meeting was started now.")
            check_periods += 1
            if check_periods >= 2:
                meeting_started = True
                logging.info("Meeting started by host.")
                break
        time.sleep(2)

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    # Check if in waiting room
    check_periods = 0
    in_waitingroom = False

    time.sleep(2)

    # Check if joined into waiting room
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'waiting_room.png'), confidence=0.9,
                                      minSearchTime=3) is not None:
        in_waitingroom = True
        logging.info("Please wait, the meeting host will let you in soon..")

    # Wait while host will let you in
    # Exit when meeting ends after time
    while in_waitingroom:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
            if DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
                atexit.unregister(os.killpg)
            return

        if pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'waiting_room.png'), confidence=0.9) is None:
            logging.info("Maybe no longer in the waiting room..")
            check_periods += 1
            if check_periods == 2:
                logging.info("No longer in the waiting room..")
                break
        time.sleep(2)

    # Meeting joined
    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    logging.info("Joined meeting..")

    # Check if recording warning is shown at the beginning
    if (pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'meeting_is_being_recorded.png'), confidence=0.9,
                                       minSearchTime=2) is not None):
        logging.info("This meeting is being recorded..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'got_it.png'), confidence=0.9)
            pyautogui.click(x, y)
            logging.info("Accepted recording..")
        except TypeError:
            logging.error("Could not accept recording!")

    # Check if host is sharing poll results at the beginning
    if (pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'host_is_sharing_poll_results.png'), confidence=0.9,
                                       minSearchTime=2) is not None):
        logging.info("Host is sharing poll results..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'host_is_sharing_poll_results.png'), confidence=0.9)
            pyautogui.click(x, y)
            try:
                x, y = pyautogui.locateCenterOnScreen(os.path.join(
                    IMG_PATH, 'exit.png'), confidence=0.9)
                pyautogui.click(x, y)
                logging.info("Closed poll results window..")
            except TypeError:
                logging.error("Could not exit poll results window!")
                if DEBUG:
                    pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                        TIME_FORMAT) + "-" + description) + "_close_poll_results_error.png")
        except TypeError:
            logging.error("Could not find poll results window anymore!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_find_poll_results_error.png")

    # Start BackgroundThread
    BackgroundThread()

    # Set computer audio
    time.sleep(2)
    if not join_audio(description):
        if not useCase == UC_CONNECTED_NOPOPUPS: 
            logging.info("Exit!")
            os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
            if DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
                atexit.unregister(os.killpg)
            time.sleep(2)
            join(meet_id, meet_pw, duration, description)

    # 'Say' something if path available (mounted)
    if os.path.exists(AUDIO_PATH):
        play_audio(description)

    time.sleep(2)
    logging.info("Enter fullscreen..")
    show_toolbars()
    try:
        x, y = pyautogui.locateCenterOnScreen(
            os.path.join(IMG_PATH, 'view.png'), confidence=0.9)
        pyautogui.click(x, y)
    except TypeError:
        logging.error("Could not find view!")
        if DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_view_error.png")

    time.sleep(2)

    fullscreen = False
    try:
        x, y = pyautogui.locateCenterOnScreen(
            os.path.join(IMG_PATH, 'fullscreen.png'), confidence=0.9)
        pyautogui.click(x, y)
        fullscreen = True
    except TypeError:
        logging.error("Could not find fullscreen!")
        if DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_fullscreen_error.png")

    # TODO: Check for 'Exit Full Screen': already fullscreen -> fullscreen = True

    # Screensharing already active
    if not fullscreen:
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'view_options.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not find view options!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_view_options_error.png")

        # Switch to fullscreen
        time.sleep(2)
        show_toolbars()

        logging.info("Enter fullscreen..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'enter_fullscreen.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not enter fullscreen by image!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_enter_fullscreen_error.png")
            return

        time.sleep(2)

    # Screensharing not active
    screensharing_active = False
    try:
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'view_options.png'), confidence=0.9)
        pyautogui.click(x, y)
        screensharing_active = True
    except TypeError:
        logging.error("Could not find view options!")
        if DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_view_options_error.png")

    time.sleep(2)

    if screensharing_active:
        # hide video panel
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'hide_video_panel.png'), confidence=0.9)
            pyautogui.click(x, y)
            VIDEO_PANEL_HIDED = True
        except TypeError:
            logging.error("Could not hide video panel!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_hide_video_panel_error.png")
    else:
        # switch to speaker view
        show_toolbars()

        logging.info("Switch view..")
        try:
            x, y = pyautogui.locateCenterOnScreen(
                os.path.join(IMG_PATH, 'view.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not find view!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_view_error.png")

        time.sleep(2)

        try:
            # speaker view
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'speaker_view.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not switch speaker view!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_speaker_view_error.png")

        try:
            # minimize panel
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'minimize.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not minimize panel!")
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_minimize_error.png")

    # Move mouse from screen
    pyautogui.moveTo(0, 100)
    pyautogui.click(0, 100)

    if DEBUG and ffmpeg_debug is not None:
        os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
        atexit.unregister(os.killpg)

    # Audio
    # Start recording
    logging.info("Start recording...")

    filename = os.path.join(REC_PATH, time.strftime(
        TIME_FORMAT) + "-" + description) + ".mkv"

    width, height = pyautogui.size()
    resolution = str(width) + 'x' + str(height)
    disp = os.getenv('DISPLAY')

    command = "ffmpeg -nostats -loglevel error -f pulse -ac 2 -i 1 -f x11grab -r 30 -s " + \
        resolution + " " + FFMPEG_INPUT_PARAMS + " -i " + disp + " " + FFMPEG_OUTPUT_PARAMS + \
        " -threads 0 -async 1 -vsync 1 \"" + filename + "\""

    ffmpeg = subprocess.Popen(
        command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(
        ffmpeg.pid), signal.SIGQUIT)

    start_date = datetime.now()
    end_date = start_date + timedelta(seconds=duration + 300)  # Add 5 minutes

    # Start thread to check active screensharing
    HideViewOptionsThread(description)
    
    # Send Telegram Notification
    send_telegram_message("Joined Meeting '{}' and started recording.".format(description))
    
    meeting_running = True
    while meeting_running:
        time_remaining = end_date - datetime.now()
        if time_remaining.total_seconds() < 0 or not ONGOING_MEETING:
            meeting_running = False
        else:
            print(f"Meeting ends in {time_remaining}", end="\r", flush=True)
        time.sleep(5)

    logging.info("Meeting ends at %s" % datetime.now())

    # Close everything
    if DEBUG and ffmpeg_debug is not None:
        os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
        atexit.unregister(os.killpg)

    os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
    os.killpg(os.getpgid(ffmpeg.pid), signal.SIGQUIT)
    atexit.unregister(os.killpg)

    if not ONGOING_MEETING:
        try:
            # Press OK after meeting ended by host
            x, y = pyautogui.locateCenterOnScreen(
                os.path.join(IMG_PATH, 'ok.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            if DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_ok_error.png")
                
    send_telegram_message("Meeting '{}' ended.".format(description))

def play_audio(description):
    # Get all files in audio directory
    files=os.listdir(AUDIO_PATH)
    # Filter .wav files
    files=list(filter(lambda f: f.endswith(".wav"), files))
    # Check if .wav files available
    if len(files) > 0:
        unmute(description)
        # Get random file
        file=random.choice(files)
        path = os.path.join(AUDIO_PATH, file)
        # Use paplay to play .wav file on specific Output
        command = "/usr/bin/paplay --device=microphone -p " + path
        play = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        res, err = play.communicate()
        if play.returncode != 0:
            logging.error("Failed playing file! - " + str(play.returncode) + " - " + str(err))
        else:
            logging.debug("Successfully played audio file! - " + str(play.returncode))
        mute(description)
    else:
        logging.error("No .wav files found!")


def exit_process_by_name(name):
    list_of_process_ids = find_process_id_by_name(name)
    if len(list_of_process_ids) > 0:
        logging.info(name + " process exists | killing..")
        for elem in list_of_process_ids:
            process_id = elem['pid']
            try:
                os.kill(process_id, signal.SIGKILL)
            except Exception as ex:
                logging.error("Could not terminate " + name +
                              "[" + str(process_id) + "]: " + str(ex))


def join_ongoing_meeting():
    with open(CSV_PATH, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=CSV_DELIMITER)
        for row in csv_reader:
            # Check and join ongoing meeting
            curr_date = datetime.now()

            weekday = check_weekday( row["weekday"], row["description"])
            if not weekday:
                return

            # Monday, tuesday, ..
            if weekday.lower() == curr_date.strftime('%A').lower():
                curr_time = curr_date.time()

                start_time_csv = datetime.strptime(row["time"], '%H:%M')
                start_date = curr_date.replace(
                    hour=start_time_csv.hour, minute=start_time_csv.minute)
                start_time = start_date.time()

                end_date = start_date + \
                    timedelta(seconds=int(row["duration"]) * 60 + 300)  # Add 5 minutes
                end_time = end_date.time()

                recent_duration = (end_date - curr_date).total_seconds()

                if start_time < end_time:
                    if start_time <= curr_time <= end_time and str(row["record"]) == 'true':
                            logging.info(
                                "Join meeting that is currently running..")
                            join(meet_id=row["id"], meet_pw=row["password"],
                                 duration=recent_duration, description=row["description"])
                else:  # crosses midnight
                    if curr_time >= start_time or curr_time <= end_time and str(row["record"]) == 'true':
                            logging.info(
                                "Join meeting that is currently running..")
                            join(meet_id=row["id"], meet_pw=row["password"],
                                 duration=recent_duration, description=row["description"])

def check_weekday( weekday, description):
    if weekday in WEEKDAYS:
        return weekday  
    else:
        # try if weekday is a date
        try:
            event_date = datetime.strptime(weekday, DATE_FORMAT)
            if (datetime.now() - event_date).days >= 1:
                # date has already passed
                logging.info("Ignoring as date %s in meeting %s is in past.", weekday, description)
                return ''
            else:
                return event_date.strftime("%A").lower()  # Monday, Tuesday, ...
        except ValueError:
            logging.error("Invalid date %s in %s.", weekday, description)
            return ''

def setup_schedule():
    schedule.clear()
    with open(CSV_PATH, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=CSV_DELIMITER)
        line_count = 0
        for row in csv_reader:
            if str(row["record"]) == 'true':
                # expand date/weekday ranges and lists
                for day in expand_days( row["weekday"]):
                    weekday = check_weekday( day, row["description"])
                    if weekday:
                        cmd_string = "schedule.every()." + weekday \
                                    + ".at(\"" \
                                    + (datetime.strptime(row["time"], '%H:%M') - timedelta(minutes=1)).strftime('%H:%M') \
                                    + "\").do(join, meet_id=\"" + row["id"] \
                                    + "\", meet_pw=\"" + row["password"] \
                                    + "\", duration=" + str(int(row["duration"]) * 60) \
                                    + ", description=\"" + row["description"] + "\")"
                        cmd = compile(cmd_string, "<string>", "eval")
                        eval(cmd)
                        line_count += 1
        logging.info("Added %s meetings to schedule." % line_count)

def start_telegram_bot():
    if not TELEGRAM_BOT_TOKEN:
        logging.info("Telegram token is missing. No Telegram bot will be started!")
        return
    
    command = f"python3 telegram_bot.py {CSV_PATH} {TELEGRAM_BOT_TOKEN}"
    telegram_bot = subprocess.Popen(
        command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

    logging.info("Telegram bot started!")

    atexit.register(os.killpg, os.getpgid(
        telegram_bot.pid), signal.SIGQUIT)
    
def start_imap_bot():
    if not (EMAIL_PASSWORD and IMAP_SERVER and IMAP_PORT and EMAIL_ADDRESS):
        logging.info("IMAP details missing. No IMAP email bot will be started!")
        return
    
    imap_log_file = open(f"{log_file}.imap_bot", "w")
    
    command = f"python3 imap_bot.py {CSV_PATH} {YAML_PATH} {IMAP_SERVER} {IMAP_PORT} {EMAIL_ADDRESS} {EMAIL_PASSWORD}"
    imap_bot = subprocess.Popen(
        command, stdout=imap_log_file, stderr=imap_log_file, shell=True, preexec_fn=os.setsid, universal_newlines=True, bufsize=1)

    logging.info("IMAP emai bot started!")

    atexit.register(os.killpg, os.getpgid(
        imap_bot.pid), signal.SIGQUIT)

def main():
    try:
        if DEBUG and not os.path.exists(DEBUG_PATH):
            os.makedirs(DEBUG_PATH)
    except Exception:
        logging.error("Failed to create screenshot folder!")
        raise

    # start bots
    start_telegram_bot()
    start_imap_bot()
        
    last_timestamp = ''
    while True:
        current_timestamp = os.path.getmtime(CSV_PATH)
        if current_timestamp != last_timestamp:
            last_timestamp = current_timestamp
            setup_schedule()
            join_ongoing_meeting()
    
        schedule.run_pending()
        time_of_next_run = schedule.next_run()
        time_now = datetime.now()
        if (time_of_next_run):
            remaining = time_of_next_run - time_now
            print(f"Next meeting in {remaining}", end="\r", flush=True)
        else:
            print(f"No meeting scheduled.", end="\r", flush=True)
        time.sleep(15)

if __name__ == '__main__':
    main()

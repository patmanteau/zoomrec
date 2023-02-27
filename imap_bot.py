import imaplib
import email
import re
import time
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from events import read_events_from_csv, write_events_to_csv, validate_event, find_event

DURATION = 75
RECORD = 'true'

# Create a dictionary to map Australian timezones to international timezones
au_tz_map = {
    'ACDT': 'Australia/Adelaide',
    'ACST': 'Australia/Darwin',
    'AEST': 'Australia/Brisbane',
    'AEDT': 'Australia/Sydney',
    'AET' : 'Australia/Hobart',
    'AWST': 'Australia/Perth'
}

def convert_short_tz( short_tz):
    return au_tz_map[short_tz]

def parse_time(time_str, pattern, day, timezone):
    time_local = datetime.strptime(time_str, pattern).replace(tzinfo=ZoneInfo(timezone))
    time_local = time_local.replace(year=day.year, month=day.month, day=day.day)
     # Convert the input time to the system timezone
    return time_local.astimezone(datetime.now().astimezone().tzinfo)

def start_bot(IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD, CSV_PATH):   
    # Loop and evaluate every new message based on the subject keyword
    while True:

        # Connect to IMAP server
        imap = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)
        resp, caps = imap.capability()
        if b'STARTTLS' in caps[0]:
            imap.starttls()
        imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        imap.select('inbox')

        # Get initial message count
        status, count = imap.status('INBOX', "(MESSAGES UNSEEN)")
        unread_count = int(count[0].split()[4].decode('utf-8').strip(').,]'))

        # Get updated message count
        status, count = imap.status('INBOX', "(MESSAGES UNSEEN)")
        new_unread_count = int(count[0].split()[4].decode('utf-8').strip(').,]'))

        # Check for new unread messages
        if new_unread_count >= unread_count:
            unread_count = new_unread_count

            # Process all unread messages
            for i in range(unread_count, 0, -1):
                _, msg_data = imap.fetch(str(i), '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                # Check the subject line for the keyword
                subject = msg['Subject']
                if 'link' in subject:

                    # Extract class information from the email body
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode('utf-8')

                            # first type
                            match = re.search(r'Your Human\.Kind Livestream - (.+) starts at ([0-9]+:[0-9]+ [AP]M) \((\S+)\)', body)
                            if match:
                                description = match.group(1)
                                description = re.sub(r'[^a-zA-Z]+', '_', description)

                                time_str = match.group(2)

                                # time_system the input time to the system timezone
                                time_system = parse_time( time_str, '%I:%M %p', datetime.now(), convert_short_tz(match.group(3)))
                                time_system_str = time_system.strftime('%H:%M')
                                date_system_str = time_system.strftime("%Y-%m-%d")

                                url_pattern = r'<(https?://\S*loyal\.im\?\S*)>'
                                match = re.search(url_pattern, body) 

                                if match:
                                    url = match.group(1)
                            
                            # second type
                            # Search for the time and description using the pattern
                            match = re.search(r'Your link to\s+(\d{1,2}(?:\.\d{2})?(?:am|pm))\s+([^\d]+)\swith\s+(.*)', subject, re.IGNORECASE)
                            if match:
                                # Extract the time and description from the match
                                time_str = match.group(1)
                                if '.' in time_str:
                                    time_pattern = '%I.%M%p'
                                else:
                                    time_pattern = '%I%p'

                                time_system = parse_time( time_str, time_pattern, datetime.now(), convert_short_tz('ACDT'))
                                time_system_str = time_system.strftime('%H:%M')
                                date_system_str = time_system.strftime("%Y-%m-%d")

                                description = match.group(2) + " " + match.group(3)
                                description = re.sub(r'[^a-zA-Z]+', '_', description)

                                # Regex pattern to match zoom links
                                ZOOM_LINK_REGEX = r"(https://.*zoom.us/\S*)"

                                # search for the pattern in the string
                                match = re.search(ZOOM_LINK_REGEX, body)
                                if match:
                                    url = match.group()

                            if url:
                                event = {'description': description, 'weekday': date_system_str, 'time': time_system_str, 'duration': DURATION, 'id': url, 'password': '', 'record': RECORD}
                                try:
                                    event = validate_event( event)
                                except ValueError as error:
                                    print( error.args[0])

                                events = read_events_from_csv(CSV_PATH)
                                events.append(event)
                                write_events_to_csv(CSV_PATH, events)

                                    

                # Mark the message as read
                imap.store(str(i), '+FLAGS', '\\Seen')

        # Close the IMAP connection
        imap.close()
        imap.logout()   

        # Wait for 5 seconds before checking again
        time.sleep(5*60)

if __name__ == "__main__":
    start_bot( CSV_PATH = sys.argv[1], IMAP_SERVER = sys.argv[2], IMAP_PORT = sys.argv[3], EMAIL_ADDRESS = sys.argv[4], EMAIL_PASSWORD = sys.argv[5])
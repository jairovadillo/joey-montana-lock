import os
import time
import re
from slackclient import SlackClient
from enum import Enum


class EnvironmentStatus(Enum):
    FREE = 0
    LOCKED = 1


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1  # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

LOCKS = {}


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"], user_id_to_username(event["user"])
    return None, None, None


def user_id_to_username(user_id):
    try:
        return slack_client.api_call('users.info', user=user_id)['user']['profile']['display_name']
    except Exception:
        return ''


def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)


def handle_command(command, channel, source_username):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try status, lock, unlock."

    # Finds and executes the given command, filling in response
    response = None

    command_words = command.split(' ')

    if len(command_words) == 2:
        command, target = command_words[0], command_words[1]

        if command == 'lock':
            if target in LOCKS.keys():
                response = "{} already locked by {}".format(target, LOCKS[target])
            else:
                LOCKS[target] = source_username
                response = "{} locked by {}".format(target, source_username)
        elif command == 'unlock':
            if target in LOCKS.keys():
                if LOCKS[target] == source_username:
                    LOCKS.pop(target, None)
                    response = "Environment {} is now free".format(target)
                else:
                    response = "You don't have permission to free and environment locked by {}".format(LOCKS[target])
            else:
                response = "{} already free".format(target)
        elif command == 'status':
            if target in LOCKS.keys():
                response = "{} locked by {}".format(target, LOCKS[target])
    elif len(command_words) == 1 and command_words[0] == 'status':
        if LOCKS:
            response = ""
            for k, v in LOCKS.items():
                response += "{} locked by {}\n".format(k, v)
        else:
            response = "All dev environments available for bananing."

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response,
        as_user=True
    )


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel, source_username = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel, source_username)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")

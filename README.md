# ArXiV-Notify

ArXiV Notify is a python 3 bot which is designed to allow you to get daily/weekly updates about papers on ArXiV.

# Setup and Installation

### 1. Clone this repository into a location of your choosing

We can clone the repository using: `git clone https://github.com/DavidMChan/ArXiV-Notify`

### 2. Install the dependencies

This library depends on the `requests` library for API calls, and the `ollama` library for summarization. Install the dependencies with:

```bash
pip install -r requirements.txt
```

### 3. Setup Telegram bot

Get the api key from botfather after creation, paste it in the .cfg, ask chatgpt how to get your msgid and voilà

### 4. Setup Ollama

Use your local instance of ollama!

### 5. Setup the config file

We need to add some details to the configuration file. Open up the arxivnotify.cfg file, it'll look something like this:
```py
#### General Configuration
# How many days of worth of papers should the bot send you?
HISTORY_DAYS = 1

#### Mailgun configuration ####
# API Key, has the format "key-********************************"
MAILGUN_API_KEY = key-********************************
# The root for mailgun, has the format "https://api.mailgun.net/v3/XXXXXX"
MAILGUN_ROOT    = https://api.mailgun.net/v3/XXXXXX
# The mailgun from email, has the format "Person Name <person_email@domain.com>"
MAILGUN_FROM    = Person Name <person_email@domain.com>
# Mailgun destination emails, have the form "person@domain.com"
MAILGUN_TO      = person@domain.com
MAILGUN_TO      = recipient_2@dummy.com

#### CLAUDE Configuration ####
# API Key for anthropic API: https://docs.anthropic.com/claude/reference/getting-started-with-the-api
CLAUDE_API_KEY = "********************************"

#### Keywords ####
# You can have as many as you like
KEYWORD = Monkey
KEYWORD = Bicycles
```

In the `MAILGUN_API_KEY` field put your API key that you got from mailgun. In the `MAILGUN_ROOT`, put that API Base URL. In the `MAILGUN_FROM`, feel free to put what you want, as long as it has the format "Name \<email\>". Put the emails that you set up as authorized recipients in the `MAILGUN_TO` key. We can handle sending to as many as you want! (though they'll all get the same email). You can then add as many `KEYWORD` fields as you like. These are the searches that will be made.

### 6. Setup a service to run the script

You can use whatever scheduler you like to run the script, but because we're big linux fans, we like using CRON. You can add a cron job for this script, `0 1 * * * python3 /path/to/arxivnotify.py`.

If you're on windows, try using the AT command: https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-2000-server/bb726974(v=technet.10)

### 7. You're Done!

Enjoy your new ArXiV bot! :D

## Using your own mail client

If you don't want to go through the setup process for mailgun, or you are averse to the service for any reason, you can replace the mailgun client with your own client. The arxivnotify.py file is well segmented, and generates a HTML string as output, which it then passes to a very simple mail sender. The string 'html_output' contains the HTML at the end of the file (before entering step 3), meaning that you can feel free to do whatever you like with this string! Write it to a file! Send it over TCP-IP. Whatever. Have fun!

# License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.



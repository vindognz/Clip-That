
# Clip That

<div align="left">
  <img src="images/icon.png" width="150" align="left" hspace="15" />

  <p>
    A Discord bot that sits in your voice call and, when someone says <strong>"clip that"</strong>, saves the last 30 seconds of the call to a <code>#clip-that</code> channel.
  </p>

  <p>
    I made it because I always wish I had been recording when a friend said something funny, and now, I'll never miss it.
  </p>

  <p>
    <strong><a href="https://youtu.be/xxPaUi_2fhY">Watch the showcase!</a></strong>
    or
    <strong><a href="https://discord.gg/RWjXsabN35">try it out!</a></strong>
  </p>
</div>
<br clear="left" />

## How it works

- Run `/listen` and the bot joins your voice channel.
- Only people who have opted in with `/opt-in` are listened to. Everyone else is ignored.
- For each opted-in person, the bot keeps only the **last 30 seconds** of audio, **in memory only**.
- Speech recognition runs locally using [Vosk](https://alphacephei.com/vosk/). No cloud services.
- When someone says "clip that" or runs `/clip`, the bot posts two files to `#clip-that`:
  - A **mixed MP3** of everyone.
  - A **ZIP archive** containing one MP3 per person.

## Using it

| Command | What it does |
|---------|--------------|
| `/opt-in` | Allow the bot to listen to you in this server |
| `/opt-out` | Stop listening to you and discard your buffered audio |
| `/listen` | Join your voice channel and start listening |
| `/unlisten` | Leave the voice channel |
| `/clip` | Save a clip immediately, without saying the phrase |
| `/dump` | Debug: export each person's buffered audio as a WAV file |
| `/ping` | Check the bot is responsive |

Typical use: everyone who's happy to be clipped runs `/opt-in`, one person runs `/listen`, and anyone opted in can say "clip that".

## Privacy

- **Opt-in only.** Everyone starts opted out.
- `/opt-out` takes effect immediately: the bot discards your buffered audio and stops using your voice for trigger detection.
- The only persistent storage is a small SQLite database (`clip_that.db`) containing the IDs of users who have opted in, per server.
- Clips are posted to `#clip-that`, which is **readable by the whole server**. The `/opt-in` message explains this.

## Requirements

- Python 3.12
- 64-bit Linux (the only platform I've tested)
- A Discord bot token
- The Opus library, if not already installed: `sudo apt install libopus0`

## Setup

### 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications), create an application, and add a **Bot**.
2. Copy its token.
3. No privileged intents are needed.
4. Invite it with the `bot` and `applications.commands` scopes and these permissions:
   - View Channels, Send Messages, Attach Files, Connect
   - **Manage Channels** (optional; only needed to create `#clip-that` automatically. Otherwise, create the channel yourself.)

### 2. Install

```bash
git clone https://github.com/vindognz/clip-that
cd clip-that
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
# If that fails, try the exact tested versions:
pip install -r requirements.lock
```

### 3. Download the speech model

```bash
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
```

Keep the extracted `vosk-model-small-en-us-0.15` folder in the project root, next to `bot.py`.

### 4. Add your token

```bash
echo 'DISCORD_TOKEN=your-bot-token-here' >> .env
```

### 5. Run

```bash
python bot.py
```

Slash commands register on startup and may take a moment to appear. Reload Discord with Ctrl+R if they don't.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The audio pipeline (buffering, mixing, encoding and zipping) and speech-recognition plumbing are tested without needing Discord or the speech model.

## Known limitations

- **Trigger accuracy varies by voice.** In my testing, roughly 3/5 triggers were caught, and it didn't work at all for one friend. It rarely false-triggers (none across several minutes of normal conversation). `/clip` is the reliable manual fallback.
- It uses the small English model for speed. A larger model might improve accuracy; change `MODEL_PATH` in `trigger.py` to try one. I haven't tested this.
- Clip length is fixed at 30 seconds.
- Tested only on Linux, in one server with a few people. Expect bugs.

Not (yet) implemented: automatic joining and leaving, configurable clip length, a spoken "clip saved" confirmation.

## Why the pinned fork?

Discord voice uses end-to-end encryption (DAVE), which many Discord libraries still struggle to receive audio from. This project pins a specific commit of a community fork of `discord-ext-voice-recv` that supports it. If you update the dependency, check that voice receiving still works.

### Thanks for voting!!!

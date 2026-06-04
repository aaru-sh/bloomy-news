# Deployment

How to keep Bloomy News running on a schedule, on every platform.
For the quick start, see the [README](../README.md).

---

## Scheduler overview

`scripts/scheduler.py` is a small foreground loop that:

- Reads `.last_run` (a JSON file with the last successful run time)
- If the last run is missing or more than 12 hours old, runs the
  pipeline now (catch-up)
- Otherwise, waits until the next **00:00** or **12:00** local time
  checkpoint
- On every run, calls `news_tool.py` and `dashboard/generate_data.py`,
  updates `.last_run` atomically

The two checkpoint hours `(0, 12)` are configurable at the top of
`scripts/scheduler.py`. Change them there if you want a different
cadence.

### Commands

```bash
python scripts/scheduler.py              # foreground loop (Ctrl-C to stop)
python scripts/scheduler.py --install    # one-time: register HKCU\...\Run\BloomyScheduler
python scripts/scheduler.py --uninstall  # remove registry entry
python scripts/scheduler.py --status     # print last-run state
python scripts/scheduler.py --run-now    # run pipeline once and exit
```

---

## Windows: autostart via the registry

```powershell
python scripts\scheduler.py --install
```

This registers `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\BloomyScheduler`
with the value:

```
C:\Path\To\pythonw.exe "E:\Path\To\bloomy-news\scripts\scheduler.py"
```

On every login, Windows starts the scheduler in the background (no
console window, `pythonw.exe`). The scheduler then loops forever,
running the pipeline at midnight and noon local time, with startup
catch-up.

To remove: `python scripts\scheduler.py --uninstall`.

The `--status` command works whether or not the scheduler is
currently running — it just reads `.last_run`.

---

## Linux: systemd user service

Create `~/.config/systemd/user/bloomy-news.service`:

```ini
[Unit]
Description=Bloomy News scheduler
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/you/bloomy-news
ExecStart=/usr/bin/python3 /home/you/bloomy-news/scripts/scheduler.py
Restart=on-failure
RestartSec=60

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now bloomy-news.service
systemctl --user status bloomy-news.service
```

To follow the log: `journalctl --user -u bloomy-news.service -f`.

---

## Linux: cron

If you prefer cron over systemd, add this to your crontab
(`crontab -e`):

```cron
0 0,12 * * * cd /home/you/bloomy-news && python news_tool.py && python dashboard/generate_data.py
```

This runs the pipeline at 00:00 and 12:00 local time, no catch-up
logic. (The scheduler's own catch-up is more graceful — use systemd
if you can.)

---

## macOS: launchd

Create `~/Library/LaunchAgents/com.bloomy-news.scheduler.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.bloomy-news.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/you/bloomy-news/scripts/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/you/bloomy-news</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/Users/you/bloomy-news/logs/launchd.out.log</string>
    <key>StandardErrorPath</key><string>/Users/you/bloomy-news/logs/launchd.err.log</string>
</dict>
</plist>
```

Then:

```bash
launchctl load ~/Library/LaunchAgents/com.bloomy-news.scheduler.plist
launchctl start com.bloomy-news.scheduler
```

---

## Telegram setup

1. Create a bot via [@BotFather](https://t.me/BotFather). Save the
   token to `.env` as `TELEGRAM_BOT_TOKEN`.
2. Create a channel, add the bot as an administrator with "post
   messages" permission.
3. Get the channel ID — send a message in the channel, then call
   `https://api.telegram.org/bot<token>/getUpdates` and read the
   `chat.id` from the response. The ID will be a negative integer
   starting with `-100` for supergroups.
4. Put the channel ID into `config/telegram.json` as
   `main_channel_id`. Add the 6 sub-channel IDs the same way (one
   per category).
5. Run `python news_tool.py` once. The digest should post within a
   few minutes.

To test the bot token without running the pipeline:

```bash
curl https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getMe
```

If that returns a JSON `ok: true`, the token is valid and you can
move on to step 3.

---

## Reverse proxy / remote access (not recommended)

By design the dashboard binds to `127.0.0.1:8080` only. Exposing it
to your LAN or the public internet would require:

- Adding authentication (none is built in)
- Switching the server to a hardened WSGI server (`gunicorn` etc.)
- Putting it behind a reverse proxy that terminates TLS
- Restating the threat model in `SECURITY.md`

None of that is in scope for this project. If you need it, fork the
project and add a `server_remote.py` rather than modifying
`dashboard/serve.py`.

# TorrentLeech Freeleech Monitor

Automated monitor for TorrentLeech that detects freeleech torrents in real-time via IRC and RSS, then automatically downloads and optionally uploads them to an FTP server.

## Features

- 🔴 **Real-time IRC monitoring** - Connects to TorrentLeech IRC #tlannounces for instant freeleech notifications
- 📡 **RSS polling** - Checks RSS feed every 30 seconds as backup
- 🎯 **Category filtering** - Monitor specific categories (Movies, Games, TV, Anime, etc.)
- 📏 **Size filtering** - Set minimum and maximum torrent sizes in GB
- ⬆️ **Auto FTP upload** - Automatically upload downloaded torrents to remote FTP server
- 🚫 **Duplicate prevention** - Tracks processed torrents to avoid re-downloading
- ⚙️ **Config file support** - Store all settings in a JSON file
- 📊 **Statistics** - Shows download counts, errors, and runtime stats

## Requirements

- Python 3.7+
- TorrentLeech account with RSS feed access
- (Optional) FTP server for automatic uploads

## Installation

1. Clone the repository:
```bash
git clone https://github.com/superlongone/torrentleech-monitor.git
cd torrentleech-monitor
```

2. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create your configuration file:
```bash
cp config.example.json config.json
```

5. Edit `config.json` with your settings:
   - Get your RSS URL from TorrentLeech website (Profile → RSS)
   - Configure FTP settings if you want auto-upload
   - Set categories and size filters as needed

## Configuration

See [CONFIG.md](CONFIG.md) for detailed configuration options.

### Quick Config Example

```json
{
  "url": "https://rss24h.torrentleech.org/YOUR_RSS_KEY",
  "categories": ["Movies", "Games"],
  "output": "./torrents",
  "min_size": 5.0,
  "max_size": 50.0,
  "ftp_host": "ftp.example.com",
  "ftp_user": "username",
  "ftp_pass": "password",
  "ftp_folder": "/path/to/upload"
}
```

## Usage

### With config file (recommended):
```bash
python monitor.py --config config.json
```

### With command line arguments:
```bash
# Monitor Movies and Games
python monitor.py --categories "Movies" "Games" --output ./torrents

# With size limits (5-50 GB)
python monitor.py --categories "Movies" --min-size 5 --max-size 50

# Disable FTP upload
python monitor.py --config config.json --no-ftp
```

### Run as background service:
```bash
# Linux/Mac
nohup python monitor.py --config config.json > monitor.log 2>&1 &

# Or using screen
screen -dmS torrent python monitor.py --config config.json
```

## Available Categories

- `Games` - All game releases
- `Movies` - All movie formats
- `TV` - TV shows and series
- `Anime` - Anime releases
- `PC-ISO` - PC game ISOs specifically
- And more (check TorrentLeech for full list)

## How It Works

1. **IRC Connection**: Connects to `irc.torrentleech.org:7021` with SSL and joins `#tlannounces`
2. **Real-time Detection**: Parses IRC announce messages for freeleech status
3. **RSS Backup**: Polls RSS feed every 30 seconds for any missed announces
4. **Filtering**: Checks category and size filters
5. **Download**: Downloads matching .torrent files to local directory
6. **FTP Upload**: (Optional) Uploads to FTP server after 5-second delay
7. **Tracking**: Marks torrents as processed to prevent duplicates

## Command Line Options

```
--config CONFIG          Path to JSON config file
--url URL               RSS feed URL
--categories CAT [CAT]  Filter by categories
--output DIR            Download directory
--irc-nick NICK         IRC nickname
--irc-pass PASS         IRC password (usually not needed)
--ftp-host HOST         FTP server hostname
--ftp-port PORT         FTP server port
--ftp-user USER         FTP username
--ftp-pass PASS         FTP password
--ftp-folder PATH       FTP upload folder
--no-ftp                Disable FTP upload
--min-size GB           Minimum torrent size in GB
--max-size GB           Maximum torrent size in GB
```

## Troubleshooting

### IRC not connecting
- Verify port 7021 is accessible
- Check if TorrentLeech IRC is online
- No password needed for IRC

### Torrents show as "unregistered"
- Ensure you're using the correct RSS key from your TorrentLeech profile
- The RSS key must match your account

### FTP upload fails
- Verify FTP credentials and folder path
- Check folder permissions on FTP server
- Monitor will fall back to current directory if target folder is inaccessible

## Statistics

The monitor displays statistics every 5 minutes showing:
- Total RSS checks performed
- Torrents found matching filters
- Torrents successfully downloaded
- Errors encountered
- Runtime duration

## Security Notes

- **Never commit `config.json`** - It contains your RSS key and FTP passwords
- Keep your RSS URL private - it's tied to your TorrentLeech account
- The `.gitignore` file excludes sensitive files by default

## License

MIT License - See LICENSE file for details

## Disclaimer

This tool is for personal use only. Ensure you comply with TorrentLeech's rules and your local laws regarding torrenting. The authors are not responsible for misuse of this software.

## Contributing

Pull requests are welcome! Please ensure:
- Code follows existing style
- New features include documentation
- No hardcoded credentials or personal data

## Author

Created for automated TorrentLeech freeleech monitoring.

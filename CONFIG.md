# TorrentLeech Monitor Configuration

This file explains how to configure the monitor with your personal settings.

## Configuration File (config.json)

Copy the example configuration and edit with your settings:

```bash
cp config.example.json config.json
```

Edit `config.json` with your settings:

```json
{
  "url": "https://rss24h.torrentleech.org/YOUR_RSS_KEY",
  "categories": ["Games", "Movies", "TV", "Anime"],
  "output": "./torrents",
  "irc_nick": "your_bot_name",
  "irc_pass": null,
  "ftp_host": "your-ftp-server.com",
  "ftp_port": 21,
  "ftp_user": "username",
  "ftp_pass": "password",
  "ftp_folder": "/path/to/upload",
  "no_ftp": false,
  "min_size": 5.0,
  "max_size": 50.0
}
```

### Configuration Options

- **url**: Your TorrentLeech RSS feed URL (get this from TorrentLeech website)
- **categories**: List of categories to monitor (e.g., "Games", "Movies", "TV", "Anime", "PC-ISO")
- **output**: Local directory where .torrent files will be saved
- **irc_nick**: IRC nickname for the bot
- **irc_pass**: IRC password (set to `null` if not needed)
- **ftp_host**: FTP server hostname
- **ftp_port**: FTP server port (usually 21)
- **ftp_user**: FTP username
- **ftp_pass**: FTP password
- **ftp_folder**: Remote folder path where torrents should be uploaded
- **no_ftp**: Set to `true` to disable FTP upload
- **min_size**: Minimum torrent size in GB (set to `null` for no limit)
- **max_size**: Maximum torrent size in GB (set to `null` for no limit)

## Usage

### With config file (recommended):
```bash
python monitor.py --config config.json
```

### Override specific settings:
```bash
# Use config but override categories
python monitor.py --config config.json --categories "Movies" "Games"

# Use config but disable FTP
python monitor.py --config config.json --no-ftp

# Use config but change size limits
python monitor.py --config config.json --min-size 10 --max-size 30
```

### Without config file:
```bash
python monitor.py --categories "Movies" --output ./torrents
```

## Security Note

**Keep your config.json file private!** It contains:
- Your RSS feed key (personal to your TorrentLeech account)
- FTP credentials

Do not commit this file to public repositories.

#!/usr/bin/env python3
"""
TorrentLeech Continuous Monitor
Continuously monitors IRC #announce and RSS feed for new freeleech torrents.
"""

import feedparser
import requests
import argparse
import sys
import re
import time
import ssl
import socket
import threading
import signal
import json
from ftplib import FTP
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
import bencodepy


class TorrentLeechIRC:
    """IRC client to monitor #announce channel for freeleech torrents."""
    
    def __init__(self, server: str = "irc.torrentleech.org", port: int = 7021, 
                 nickname: str = None, password: str = None, use_ssl: bool = True,
                 on_freeleech_callback=None):
        self.server = server
        self.port = port
        self.nickname = nickname or f"tlrss_{int(time.time())}"
        self.password = password
        self.use_ssl = use_ssl
        self.socket = None
        self.connected = False
        self.freeleech_torrents: Set[str] = set()
        self.running = False
        self.monitor_thread = None
        self.channel = "#tlannounces"
        self.on_freeleech_callback = on_freeleech_callback
        
    def connect(self) -> bool:
        """Connect to IRC server with SSL."""
        try:
            print(f"[IRC] Connecting to {self.server}:{self.port}...")
            
            # Create socket
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.settimeout(30)
            
            # Wrap with SSL if enabled
            if self.use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                self.socket = context.wrap_socket(raw_socket, server_hostname=self.server)
            else:
                self.socket = raw_socket
            
            # Connect
            self.socket.connect((self.server, self.port))
            
            # Send NICK and USER (PASS before NICK if password provided)
            if self.password:
                print(f"  Authenticating with password...")
                self.send(f"PASS {self.password}")
                time.sleep(0.5)
            
            self.send(f"NICK {self.nickname}")
            self.send(f"USER {self.nickname} 0 * :{self.nickname}")
            
            # Wait for registration to complete
            print("  Waiting for registration...")
            time.sleep(10)
            
            # Read and respond to initial messages (including PING)
            for i in range(10):
                lines = self._read_lines(timeout=0.5)
                for line in lines:
                    if line.startswith('PING'):
                        self.send(line.replace('PING', 'PONG'))
                time.sleep(0.3)
            
            # Join channel
            print(f"  Joining {self.channel}...")
            self.send(f"JOIN {self.channel}")
            time.sleep(2)
            self._read_lines(timeout=1)
            
            self.connected = True
            print(f"[IRC] ✓ Connected and joined {self.channel}")
            return True
            
        except Exception as e:
            print(f"[IRC] Error connecting: {e}")
            return False
    
    def send(self, message: str):
        """Send a message to the IRC server."""
        try:
            self.socket.send(f"{message}\r\n".encode('utf-8'))
        except Exception as e:
            print(f"[IRC] Error sending message: {e}")
    
    def _read_lines(self, timeout: float = 0.1) -> List[str]:
        """Read available lines from IRC server."""
        lines = []
        self.socket.settimeout(timeout)
        try:
            while True:
                data = self.socket.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                lines.extend(data.split('\r\n'))
        except socket.timeout:
            pass
        except Exception:
            pass
        return [line for line in lines if line]
    
    def parse_announce_message(self, message: str) -> Optional[Dict]:
        """Parse announce message for torrent info and freeleech status."""
        try:
            # Example format from #tlannounces:
            # :_AnnounceBot_!Announce@torrentleech.org PRIVMSG #tlannounces :00,04New Torrent Announcement:00,12 <Category>  Name:'Title' uploaded by 'User' freeleech - 01,15 https://www.torrentleech.org/torrent/ID
            
            # Extract torrent ID from URL
            id_match = re.search(r'torrent[:/](\d+)', message)
            if not id_match:
                return None
            
            torrent_id = id_match.group(1)
            
            # Extract category (between < >)
            category_match = re.search(r'<([^>]+)>', message)
            category = category_match.group(1).strip() if category_match else None
            
            # Extract title (between Name:' and ')
            title_match = re.search(r"Name:'([^']+)'", message)
            title = title_match.group(1).strip() if title_match else None
            
            # Check for freeleech - must be as a standalone word, not part of another word
            # The word "freeleech" appears between "uploaded by 'User'" and the URL
            # Example: "uploaded by 'Anonymous' freeleech - https://..."
            # Use word boundary to avoid matching "FREQUENCY" or similar
            freeleech = bool(re.search(r"uploaded by '[^']+' freeleech\s", message, re.IGNORECASE))
            
            return {
                'id': torrent_id,
                'freeleech': freeleech,
                'category': category,
                'title': title,
                'message': message,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            return None
    
    def start_monitor(self):
        """Start monitoring in background thread."""
        if self.running:
            return
        
        self.running = True
        
        def monitor_loop():
            self.socket.settimeout(1)
            reconnect_attempts = 0
            max_reconnect = 5
            
            while self.running:
                try:
                    if not self.connected:
                        if reconnect_attempts < max_reconnect:
                            print(f"[IRC] Attempting to reconnect ({reconnect_attempts + 1}/{max_reconnect})...")
                            if self.connect():
                                reconnect_attempts = 0
                            else:
                                reconnect_attempts += 1
                                time.sleep(3)
                        else:
                            print("[IRC] Max reconnection attempts reached. Stopping IRC monitor.")
                            break
                        continue
                    
                    lines = self._read_lines(timeout=1)
                    for line in lines:
                        if line.startswith('PING'):
                            self.send(line.replace('PING', 'PONG'))
                        elif 'PRIVMSG' in line and self.channel in line:
                            announce_info = self.parse_announce_message(line)
                            if announce_info:
                                self.freeleech_torrents.add(announce_info['id'])
                                timestamp = announce_info['timestamp'].strftime('%H:%M:%S')
                                category = announce_info.get('category', 'Unknown')
                                title = announce_info.get('title', 'Unknown')[:60]
                                print(f"[IRC] [{timestamp}] ✓ Freeleech: [{category}] {title}... (ID: {announce_info['id']})")
                                
                                # Callback for immediate processing
                                if self.on_freeleech_callback:
                                    self.on_freeleech_callback(announce_info)
                
                except socket.error:
                    print("[IRC] Connection lost. Will attempt to reconnect...")
                    self.connected = False
                    try:
                        self.socket.close()
                    except:
                        pass
                except Exception as e:
                    print(f"[IRC] Error in monitor loop: {e}")
                    time.sleep(5)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[IRC] Background monitor started")
    
    def stop_monitor(self):
        """Stop background monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def is_freeleech(self, torrent_id: str) -> bool:
        """Check if a torrent ID is in the freeleech set."""
        return torrent_id in self.freeleech_torrents
    
    def disconnect(self):
        """Disconnect from IRC server."""
        if self.connected:
            try:
                self.send("QUIT :Goodbye")
                self.socket.close()
            except:
                pass
            self.connected = False


class TorrentMonitor:
    """Main monitor class that coordinates IRC and RSS checking."""
    
    def __init__(self, rss_url: str, categories: List[str] = None, 
                 download_dir: str = ".", irc_nick: str = None, irc_pass: str = None,
                 ftp_host: str = None, ftp_port: int = 21, ftp_user: str = None, 
                 ftp_pass: str = None, ftp_folder: str = "/",
                 min_size: float = None, max_size: float = None):
        self.rss_url = rss_url
        self.categories = categories
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.min_size = min_size  # Size in GB
        self.max_size = max_size  # Size in GB
        
        # FTP settings
        self.ftp_host = ftp_host
        self.ftp_port = ftp_port
        self.ftp_user = ftp_user
        self.ftp_pass = ftp_pass
        self.ftp_folder = ftp_folder
        self.ftp_enabled = bool(ftp_host and ftp_user and ftp_pass)
        
        # Track processed torrents to avoid duplicates
        self.processed_torrents: Set[str] = set()
        self.last_rss_check = 0
        self.running = False
        
        # Statistics
        self.stats = {
            'rss_checks': 0,
            'torrents_found': 0,
            'torrents_downloaded': 0,
            'errors': 0,
            'started_at': datetime.now()
        }
        
        # Initialize IRC client
        self.irc_client = TorrentLeechIRC(
            nickname=irc_nick,
            password=irc_pass,
            on_freeleech_callback=self.on_freeleech_announce
        )
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def on_freeleech_announce(self, announce_info: Dict):
        """Callback when IRC detects a new freeleech announce."""
        torrent_id = announce_info['id']
        
        # Check if already processed
        if torrent_id in self.processed_torrents:
            return
        
        # Only process if it's freeleech
        if not announce_info.get('freeleech'):
            return
        
        # Check category filter
        if self.categories and announce_info.get('category'):
            # Category from IRC might have " :: " format like "TV :: Episodes HD"
            announce_cat = announce_info['category']
            if not any(cat.lower() in announce_cat.lower() for cat in self.categories):
                return
        
        # Mark as processed
        self.processed_torrents.add(torrent_id)
        self.stats['torrents_found'] += 1
        
        title = announce_info.get('title', f'torrent_{torrent_id}')
        print(f"[IRC] ✓ Freeleech match: [{announce_info.get('category', 'Unknown')}] {title[:60]}...")
        
        # Build download URL using RSS key from feed URL
        # Format: https://www.torrentleech.org/rss/download/TORRENTID/RSSKEY/filename.torrent
        rss_key = self.rss_url.split('/')[-1]
        
        # Sanitize title for URL
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        safe_title = safe_title[:200]  # Limit length
        
        download_url = f"https://www.torrentleech.org/rss/download/{torrent_id}/{rss_key}/{safe_title}.torrent"
        
        # Check size if filters are set
        if self.min_size is not None or self.max_size is not None:
            size_gb = self.get_torrent_size(download_url)
            if size_gb is not None:
                if self.min_size is not None and size_gb < self.min_size:
                    print(f"[IRC] ✗ Skipped (too small: {size_gb:.2f} GB < {self.min_size} GB): {title[:40]}...")
                    return
                if self.max_size is not None and size_gb > self.max_size:
                    print(f"[IRC] ✗ Skipped (too large: {size_gb:.2f} GB > {self.max_size} GB): {title[:40]}...")
                    return
                print(f"[IRC] Size: {size_gb:.2f} GB")
        
        # Download immediately
        self.download_torrent(download_url, title)
    
    def check_rss_feed(self):
        """Check RSS feed for new torrents."""
        try:
            self.stats['rss_checks'] += 1
            
            feed = feedparser.parse(self.rss_url)
            
            if not feed.entries:
                return
            
            new_found = 0
            
            for entry in feed.entries:
                # Extract torrent ID
                torrent_id = None
                if hasattr(entry, 'id'):
                    torrent_id = entry.id.split('/')[-1]
                
                if not torrent_id or torrent_id in self.processed_torrents:
                    continue
                
                # Parse category
                category = 'Unknown'
                if hasattr(entry, 'tags') and entry.tags:
                    category = entry.tags[0].get('term', 'Unknown')
                
                # Check category filter
                if self.categories:
                    if not any(cat.lower() in category.lower() for cat in self.categories):
                        continue
                
                # Check if freeleech (from IRC data)
                if not self.irc_client.is_freeleech(torrent_id):
                    continue
                
                # Mark as processed
                self.processed_torrents.add(torrent_id)
                new_found += 1
                self.stats['torrents_found'] += 1
                
                # Download
                title = entry.get('title', f'torrent_{torrent_id}')
                link = entry.get('link', '')
                
                if link:
                    # Check size if filters are set
                    skip = False
                    if self.min_size is not None or self.max_size is not None:
                        size_gb = self.get_torrent_size(link)
                        if size_gb is not None:
                            if self.min_size is not None and size_gb < self.min_size:
                                print(f"[RSS] ✗ Skipped (too small: {size_gb:.2f} GB < {self.min_size} GB): {title[:40]}...")
                                skip = True
                            elif self.max_size is not None and size_gb > self.max_size:
                                print(f"[RSS] ✗ Skipped (too large: {size_gb:.2f} GB > {self.max_size} GB): {title[:40]}...")
                                skip = True
                            else:
                                print(f"[RSS] ✓ New freeleech: [{category}] {title[:60]}... ({size_gb:.2f} GB)")
                    
                    if not skip:
                        if self.min_size is None and self.max_size is None:
                            print(f"[RSS] ✓ New freeleech: [{category}] {title[:60]}...")
                        self.download_torrent(link, title)
                else:
                    print(f"[RSS] Warning: No download link for {title[:40]}")
            
            if new_found > 0:
                print(f"[RSS] Found {new_found} new freeleech torrents")
                
        except Exception as e:
            print(f"[RSS] Error checking feed: {e}")
            self.stats['errors'] += 1
    
    def get_torrent_size(self, url: str) -> Optional[float]:
        """Download torrent file temporarily and get its size in GB."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse torrent file
            torrent_data = bencodepy.decode(response.content)
            
            # Calculate total size
            total_size = 0
            if b'info' in torrent_data:
                info = torrent_data[b'info']
                
                # Single file torrent
                if b'length' in info:
                    total_size = info[b'length']
                # Multi-file torrent
                elif b'files' in info:
                    for file_info in info[b'files']:
                        total_size += file_info[b'length']
            
            # Convert bytes to GB
            size_gb = total_size / (1024 ** 3)
            return size_gb
            
        except Exception as e:
            print(f"[SIZE] Error getting torrent size: {e}")
            return None
    
    def upload_to_ftp(self, filepath: Path) -> bool:
        """Upload a file to FTP server."""
        if not self.ftp_enabled:
            return False
        
        try:
            print(f"[FTP] Uploading {filepath.name} to {self.ftp_host}:{self.ftp_port}{self.ftp_folder}")
            
            # Connect to FTP
            ftp = FTP()
            ftp.connect(self.ftp_host, self.ftp_port, timeout=30)
            ftp.login(self.ftp_user, self.ftp_pass)
            
            # Check current directory
            current_dir = ftp.pwd()
            print(f"[FTP] Current directory: {current_dir}")
            
            # Change to target directory
            try:
                ftp.cwd(self.ftp_folder)
                print(f"[FTP] Changed to directory: {self.ftp_folder}")
            except Exception as cwd_err:
                print(f"[FTP] Could not change to {self.ftp_folder}: {cwd_err}")
                # List available directories
                try:
                    print(f"[FTP] Available in {current_dir}:")
                    ftp.retrlines('LIST')
                except:
                    pass
                # Try to create the directory
                try:
                    print(f"[FTP] Attempting to create directory: {self.ftp_folder}")
                    ftp.mkd(self.ftp_folder)
                    ftp.cwd(self.ftp_folder)
                    print(f"[FTP] Created and changed to {self.ftp_folder}")
                except Exception as mk_err:
                    print(f"[FTP] Could not create directory: {mk_err}")
                    # Upload to current directory instead
                    print(f"[FTP] Uploading to current directory: {current_dir}")
            
            # Upload file
            with open(filepath, 'rb') as f:
                ftp.storbinary(f'STOR {filepath.name}', f)
            
            ftp.quit()
            print(f"[FTP] ✓ Uploaded successfully")
            return True
            
        except Exception as e:
            print(f"[FTP] Error uploading {filepath.name}: {e}")
            self.stats['errors'] += 1
            return False
    
    def download_torrent(self, url: str, title: str) -> bool:
        """Download a torrent file and upload to FTP if configured."""
        try:
            # Sanitize filename
            filename = re.sub(r'[<>:"/\\|?*]', '_', title)
            filename = filename[:200]  # Limit length
            if not filename.endswith('.torrent'):
                filename += '.torrent'
            
            filepath = self.download_dir / filename
            
            # Download
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[DOWNLOAD] [{timestamp}] ✓ {filename}")
            self.stats['torrents_downloaded'] += 1
            
            # Upload to FTP if enabled
            if self.ftp_enabled:
                print(f"[FTP] Waiting 5 seconds before upload...")
                time.sleep(5)
                self.upload_to_ftp(filepath)
            
            return True
            
        except Exception as e:
            print(f"[DOWNLOAD] Error downloading {title[:40]}: {e}")
            self.stats['errors'] += 1
            return False
    
    def print_stats(self):
        """Print statistics."""
        runtime = datetime.now() - self.stats['started_at']
        hours = int(runtime.total_seconds() // 3600)
        minutes = int((runtime.total_seconds() % 3600) // 60)
        
        print(f"\n{'='*70}")
        print(f"STATISTICS (Runtime: {hours}h {minutes}m)")
        print(f"{'='*70}")
        print(f"RSS Checks:           {self.stats['rss_checks']}")
        print(f"Torrents Found:       {self.stats['torrents_found']}")
        print(f"Torrents Downloaded:  {self.stats['torrents_downloaded']}")
        print(f"Errors:               {self.stats['errors']}")
        print(f"Processed IDs:        {len(self.processed_torrents)}")
        print(f"Download Directory:   {self.download_dir}")
        if self.categories:
            print(f"Categories Filter:    {', '.join(self.categories)}")
        print(f"{'='*70}\n")
    
    def run(self):
        """Main monitoring loop."""
        self.running = True
        
        # Connect to IRC
        print("\n[MONITOR] Starting continuous monitor...")
        print(f"[MONITOR] Download directory: {self.download_dir}")
        if self.categories:
            print(f"[MONITOR] Filtering categories: {', '.join(self.categories)}")
        if self.min_size is not None:
            print(f"[MONITOR] Minimum size: {self.min_size} GB")
        if self.max_size is not None:
            print(f"[MONITOR] Maximum size: {self.max_size} GB")
        print(f"[MONITOR] RSS check interval: 30 seconds (2x per minute)")
        if self.ftp_enabled:
            print(f"[MONITOR] FTP upload enabled: {self.ftp_user}@{self.ftp_host}:{self.ftp_port}{self.ftp_folder}")
        else:
            print(f"[MONITOR] FTP upload disabled")
        print()
        
        if self.irc_client.connect():
            self.irc_client.start_monitor()
        else:
            print("[MONITOR] Warning: IRC connection failed. Only RSS monitoring will work.")
        
        print("[MONITOR] ✓ Monitor is running. Press Ctrl+C to stop.\n")
        
        last_stats_print = time.time()
        
        try:
            while self.running:
                # Check RSS feed every 30 seconds (2x per minute)
                current_time = time.time()
                if current_time - self.last_rss_check >= 30:
                    self.check_rss_feed()
                    self.last_rss_check = current_time
                
                # Print stats every 5 minutes
                if current_time - last_stats_print >= 300:
                    self.print_stats()
                    last_stats_print = current_time
                
                # Sleep briefly
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n[MONITOR] Shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        self.irc_client.stop_monitor()
        self.irc_client.disconnect()
        self.print_stats()
        print("[MONITOR] Stopped.")


def main():
    parser = argparse.ArgumentParser(
        description='Continuously monitor TorrentLeech for freeleech torrents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use config file
  python monitor.py --config config.json
  
  # Monitor PC-ISO category
  python monitor.py --categories "PC-ISO"
  
  # Monitor multiple categories
  python monitor.py --categories "Movies" "Anime" "PC-ISO"
  
  # Specify download directory
  python monitor.py --categories "Movies" --output /path/to/torrents
  
  # With custom IRC nick
  python monitor.py --categories "PC-ISO" --irc-nick "your_nick"

The monitor will:
  1. Connect to IRC #tlannounces and listen for freeleech announces (real-time)
  2. Check RSS feed every 30 seconds (2x per minute)
  3. Download matching freeleech torrents automatically
  4. Skip duplicates
  5. Print statistics periodically
        """
    )
    
    parser.add_argument(
        '--config',
        help='Path to JSON config file (overrides other arguments)'
    )
    
    parser.add_argument(
        '--url',
        help='RSS feed URL'
    )
    
    parser.add_argument(
        '--categories', '-c',
        nargs='+',
        help='Filter by categories'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Download directory'
    )
    
    parser.add_argument(
        '--irc-nick',
        help='IRC nickname'
    )
    
    parser.add_argument(
        '--irc-pass',
        help='IRC password (if required)'
    )
    
    parser.add_argument(
        '--ftp-host',
        help='FTP server host'
    )
    
    parser.add_argument(
        '--ftp-port',
        type=int,
        help='FTP server port'
    )
    
    parser.add_argument(
        '--ftp-user',
        help='FTP username'
    )
    
    parser.add_argument(
        '--ftp-pass',
        help='FTP password'
    )
    
    parser.add_argument(
        '--ftp-folder',
        help='FTP upload folder'
    )
    
    parser.add_argument(
        '--no-ftp',
        action='store_true',
        help='Disable FTP upload'
    )
    
    parser.add_argument(
        '--min-size',
        type=float,
        help='Minimum torrent size in GB'
    )
    
    parser.add_argument(
        '--max-size',
        type=float,
        help='Maximum torrent size in GB'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            print(f"[CONFIG] Loaded configuration from {args.config}")
        except Exception as e:
            print(f"[CONFIG] Error loading config file: {e}")
            sys.exit(1)
    
    # Merge config file with command line args (command line takes precedence)
    url = args.url or config.get('url')
    categories = args.categories or config.get('categories')
    output = args.output or config.get('output', './torrents')
    irc_nick = args.irc_nick or config.get('irc_nick')
    irc_pass = args.irc_pass or config.get('irc_pass')
    ftp_host = args.ftp_host or config.get('ftp_host')
    ftp_port = args.ftp_port or config.get('ftp_port')
    ftp_user = args.ftp_user or config.get('ftp_user')
    ftp_pass = args.ftp_pass or config.get('ftp_pass')
    ftp_folder = args.ftp_folder or config.get('ftp_folder')
    no_ftp = args.no_ftp or config.get('no_ftp', False)
    min_size = args.min_size or config.get('min_size')
    max_size = args.max_size or config.get('max_size')
    
    # Create monitor
    monitor = TorrentMonitor(
        rss_url=url,
        categories=categories,
        download_dir=output,
        irc_nick=irc_nick,
        irc_pass=irc_pass,
        ftp_host=None if no_ftp else ftp_host,
        ftp_port=ftp_port,
        ftp_user=ftp_user,
        ftp_pass=ftp_pass,
        ftp_folder=ftp_folder,
        min_size=min_size,
        max_size=max_size
    )
    
    # Handle signals for clean shutdown
    def signal_handler(sig, frame):
        print("\n[SIGNAL] Received shutdown signal")
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run
    monitor.run()


if __name__ == '__main__':
    main()

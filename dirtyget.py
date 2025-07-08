#!/usr/bin/env python3
"""
Podcast downloader that uses dirtyget configuration format.
Downloads the newest episodes for each podcast.
"""

import os
import sys
import re
import configparser
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from pathlib import Path
import time
from datetime import datetime
import argparse
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TPE1, TALB, TCON, TIT2, COMM


class PodcastDownloader:
    def __init__(self, config_file=None, force_overwrite=False):
        self.config_file = config_file or os.path.expanduser("~/.dirtygetrc")
        self.config = configparser.ConfigParser(interpolation=None)  # Disable interpolation
        self.config.optionxform = str  # Preserve case sensitivity
        self.force_overwrite = force_overwrite
        self.downloaded_urls_file = os.path.expanduser("~/.dirtyget_downloaded_urls")
        self.downloaded_urls = set()
        
    def load_config(self):
        """Load dirtyget configuration file."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        self.config.read(self.config_file)
    
    def load_downloaded_urls(self):
        """Load previously downloaded URLs from file."""
        if os.path.exists(self.downloaded_urls_file):
            try:
                with open(self.downloaded_urls_file, 'r') as f:
                    self.downloaded_urls = set(line.strip() for line in f if line.strip())
            except IOError as e:
                print(f"Warning: Could not read downloaded URLs file: {e}")
                self.downloaded_urls = set()
        else:
            self.downloaded_urls = set()
    
    def save_downloaded_url(self, url):
        """Save a downloaded URL to the tracking file."""
        if url not in self.downloaded_urls:
            self.downloaded_urls.add(url)
            try:
                with open(self.downloaded_urls_file, 'a') as f:
                    f.write(f"{url}\n")
            except IOError as e:
                print(f"Warning: Could not save downloaded URL: {e}")
        
    def get_channels(self):
        """Get all podcast channels from configuration."""
        channels = {}
        global_config = {}
        
        # Get global configuration if [*] section exists
        if '*' in self.config.sections():
            global_config = dict(self.config['*'])
        
        # Process each channel
        for section in self.config.sections():
            if section == '*':
                continue
                
            channel_config = dict(global_config)  # Start with global config
            channel_config.update(dict(self.config[section]))  # Override with channel-specific
            
            if 'url' not in channel_config:
                print(f"Warning: No URL specified for channel '{section}', skipping")
                continue
                
            channels[section] = channel_config
            
        return channels
    
    def parse_rss_feed(self, url, max_episodes=1):
        """Parse RSS feed and return specified number of episodes."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # Find all items in the RSS feed
            items = root.findall('.//item')
            
            if not items:
                print(f"No episodes found in feed: {url}")
                return []
            
            # Get the requested number of episodes (or all available if fewer)
            episodes_to_process = items[:max_episodes]
            episodes = []
            
            for item in episodes_to_process:
                # Extract episode information
                episode = {
                    'title': self._get_text(item, 'title'),
                    'description': self._get_text(item, 'description'),
                    'pub_date': self._get_text(item, 'pubDate'),
                    'link': self._get_text(item, 'link'),
                    'enclosure_url': None,
                    'enclosure_type': None,
                    'enclosure_length': None
                }
                
                # Find enclosure (audio/video file)
                enclosure = item.find('enclosure')
                if enclosure is not None:
                    episode['enclosure_url'] = enclosure.get('url')
                    episode['enclosure_type'] = enclosure.get('type')
                    episode['enclosure_length'] = enclosure.get('length')
                
                episodes.append(episode)
            
            return episodes
            
        except requests.RequestException as e:
            print(f"Error fetching RSS feed {url}: {e}")
            return []
        except ET.ParseError as e:
            print(f"Error parsing RSS feed {url}: {e}")
            return []
    
    def _get_text(self, element, tag):
        """Get text content from XML element."""
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ""
    
    def download_episode(self, episode, channel_name, channel_config):
        """Download a single episode."""
        if not episode['enclosure_url']:
            print(f"No download URL found for episode: {episode['title']}")
            return False
        
        # Check if URL has been downloaded before (unless --force is used)
        if not self.force_overwrite and episode['enclosure_url'] in self.downloaded_urls:
            print(f"Episode URL already downloaded (skipping): {episode['title']}")
            return True
        
        # Determine download directory
        spool_dir = channel_config.get('spool', os.getcwd())
        download_dir = Path(spool_dir)
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = self._generate_filename(episode, channel_name, channel_config)
        filepath = download_dir / filename
        
        # Check if file already exists
        if filepath.exists() and not self.force_overwrite:
            print(f"Episode already downloaded: {filepath}")
            # Still save the URL to tracking file if not already there
            self.save_downloaded_url(episode['enclosure_url'])
            return True
        elif filepath.exists() and self.force_overwrite:
            print(f"Overwriting existing file: {filepath}")
        
        # Download the file
        try:
            print(f"Downloading: {episode['title']}")
            response = requests.get(episode['enclosure_url'], stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"Downloaded: {filepath}")
            
            # Save URL to tracking file
            self.save_downloaded_url(episode['enclosure_url'])
            
            # Set metadata tags
            self._set_metadata_tags(filepath, episode, channel_name, channel_config)
            
            # Update playlist if specified
            if 'playlist' in channel_config:
                self._update_playlist(filepath, channel_config['playlist'])
            
            return True
            
        except requests.RequestException as e:
            print(f"Error downloading episode: {e}")
            return False
        except IOError as e:
            print(f"Error writing file: {e}")
            return False
    
    def _generate_filename(self, episode, channel_name, channel_config):
        """Generate filename for downloaded episode."""
        # Check if custom filespec is provided
        if 'filespec' in channel_config:
            # This is a simplified implementation
            # In a full implementation, you'd handle %(date), %(title) etc.
            return channel_config['filespec']
        
        # Default filename generation
        title = episode['title']
        # Clean title for filename
        title = re.sub(r'[^\w\-_\.]', '_', title)
        
        # Get file extension from URL
        parsed_url = urlparse(episode['enclosure_url'])
        path = parsed_url.path
        ext = os.path.splitext(path)[1] or '.mp3'
        
        return f"{channel_name}_{title}{ext}"
    
    def _set_metadata_tags(self, filepath, episode, channel_name, channel_config):
        """Set metadata tags on the downloaded file."""
        try:
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                print(f"Warning: Could not read metadata for {filepath}")
                return
            
            # Handle ID3 tags for MP3 files
            if filepath.suffix.lower() == '.mp3':
                if not hasattr(audio_file, 'tags') or audio_file.tags is None:
                    audio_file.add_tags()
                
                tags = audio_file.tags
                
                # Set title if not present
                if 'TIT2' not in tags:
                    tags['TIT2'] = TIT2(encoding=3, text=episode['title'])
                
                # Set artist if not present - use channel name as reasonable default
                if 'TPE1' not in tags:
                    default_artist = channel_config.get('artist_tag', channel_name.title())
                    tags['TPE1'] = TPE1(encoding=3, text=default_artist)
                
                # Set album if specified in config
                if 'album_tag' in channel_config:
                    tags['TALB'] = TALB(encoding=3, text=channel_config['album_tag'])
                
                # Set genre if specified in config
                if 'genre_tag' in channel_config:
                    tags['TCON'] = TCON(encoding=3, text=channel_config['genre_tag'])
                elif 'genre' in channel_config:
                    tags['TCON'] = TCON(encoding=3, text=channel_config['genre'])
                
                # Set comment if specified in config
                if 'comment_tag' in channel_config:
                    tags['COMM'] = COMM(encoding=3, lang='eng', desc='', text=channel_config['comment_tag'])
                
                audio_file.save()
                print(f"Updated metadata for: {filepath}")
            
            else:
                # Handle other audio formats (MP4, OGG, etc.)
                if audio_file.tags is None:
                    audio_file.add_tags()
                
                tags = audio_file.tags
                
                # Set title if not present
                if 'TITLE' not in tags:
                    tags['TITLE'] = episode['title']
                
                # Set artist if not present
                if 'ARTIST' not in tags:
                    default_artist = channel_config.get('artist_tag', channel_name.title())
                    tags['ARTIST'] = default_artist
                
                # Set album if specified in config
                if 'album_tag' in channel_config:
                    tags['ALBUM'] = channel_config['album_tag']
                
                # Set genre if specified in config
                if 'genre_tag' in channel_config:
                    tags['GENRE'] = channel_config['genre_tag']
                elif 'genre' in channel_config:
                    tags['GENRE'] = channel_config['genre']
                
                audio_file.save()
                print(f"Updated metadata for: {filepath}")
                
        except Exception as e:
            print(f"Error setting metadata for {filepath}: {e}")
    
    def _update_playlist(self, filepath, playlist_path):
        """Update M3U playlist file."""
        try:
            with open(playlist_path, 'a') as f:
                f.write(f"{filepath}\n")
        except IOError as e:
            print(f"Error updating playlist: {e}")
    
    def download_all_latest(self):
        """Download episodes for all configured channels."""
        self.load_config()
        self.load_downloaded_urls()
        channels = self.get_channels()
        
        if not channels:
            print("No channels configured")
            return
        
        print(f"Found {len(channels)} channels")
        
        for channel_name, channel_config in channels.items():
            print(f"\nProcessing channel: {channel_name}")
            
            # Determine number of episodes to download
            max_episodes = int(channel_config.get('max_episodes', 1))
            
            # Parse RSS feed
            episodes = self.parse_rss_feed(channel_config['url'], max_episodes)
            if not episodes:
                continue
            
            print(f"Found {len(episodes)} episode(s) to process")
            
            # Download episodes
            for i, episode in enumerate(episodes, 1):
                print(f"  Episode {i}/{len(episodes)}: {episode['title']}")
                self.download_episode(episode, channel_name, channel_config)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Download podcasts using dirtyget configuration')
    parser.add_argument('config_file', nargs='?', default=None,
                        help='Path to dirtyget configuration file (default: ~/.dirtygetrc)')
    parser.add_argument('--force', action='store_true',
                        help='Force overwrite existing downloaded files')
    
    args = parser.parse_args()
    
    downloader = PodcastDownloader(args.config_file, args.force)
    downloader.download_all_latest()


if __name__ == "__main__":
    main()
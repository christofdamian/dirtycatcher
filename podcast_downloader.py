#!/usr/bin/env python3
"""
Podcast downloader that uses castget configuration format.
Downloads only the newest episode for each podcast.
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


class PodcastDownloader:
    def __init__(self, config_file=None):
        self.config_file = config_file or os.path.expanduser("~/.castgetrc")
        self.config = configparser.ConfigParser(interpolation=None)  # Disable interpolation
        self.config.optionxform = str  # Preserve case sensitivity
        
    def load_config(self):
        """Load castget configuration file."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        self.config.read(self.config_file)
        
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
    
    def parse_rss_feed(self, url):
        """Parse RSS feed and return latest episode."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # Find all items in the RSS feed
            items = root.findall('.//item')
            
            if not items:
                print(f"No episodes found in feed: {url}")
                return None
            
            # Get the first item (latest episode)
            latest_item = items[0]
            
            # Extract episode information
            episode = {
                'title': self._get_text(latest_item, 'title'),
                'description': self._get_text(latest_item, 'description'),
                'pub_date': self._get_text(latest_item, 'pubDate'),
                'link': self._get_text(latest_item, 'link'),
                'enclosure_url': None,
                'enclosure_type': None,
                'enclosure_length': None
            }
            
            # Find enclosure (audio/video file)
            enclosure = latest_item.find('enclosure')
            if enclosure is not None:
                episode['enclosure_url'] = enclosure.get('url')
                episode['enclosure_type'] = enclosure.get('type')
                episode['enclosure_length'] = enclosure.get('length')
            
            return episode
            
        except requests.RequestException as e:
            print(f"Error fetching RSS feed {url}: {e}")
            return None
        except ET.ParseError as e:
            print(f"Error parsing RSS feed {url}: {e}")
            return None
    
    def _get_text(self, element, tag):
        """Get text content from XML element."""
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ""
    
    def download_episode(self, episode, channel_name, channel_config):
        """Download a single episode."""
        if not episode['enclosure_url']:
            print(f"No download URL found for episode: {episode['title']}")
            return False
        
        # Determine download directory
        spool_dir = channel_config.get('spool', os.getcwd())
        download_dir = Path(spool_dir)
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = self._generate_filename(episode, channel_name, channel_config)
        filepath = download_dir / filename
        
        # Check if file already exists
        if filepath.exists():
            print(f"Episode already downloaded: {filepath}")
            return True
        
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
    
    def _update_playlist(self, filepath, playlist_path):
        """Update M3U playlist file."""
        try:
            with open(playlist_path, 'a') as f:
                f.write(f"{filepath}\n")
        except IOError as e:
            print(f"Error updating playlist: {e}")
    
    def download_all_latest(self):
        """Download the latest episode for all configured channels."""
        self.load_config()
        channels = self.get_channels()
        
        if not channels:
            print("No channels configured")
            return
        
        print(f"Found {len(channels)} channels")
        
        for channel_name, channel_config in channels.items():
            print(f"\nProcessing channel: {channel_name}")
            
            # Parse RSS feed
            episode = self.parse_rss_feed(channel_config['url'])
            if not episode:
                continue
            
            # Download episode
            self.download_episode(episode, channel_name, channel_config)


def main():
    """Main function."""
    config_file = None
    
    # Check for command line argument
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    downloader = PodcastDownloader(config_file)
    downloader.download_all_latest()


if __name__ == "__main__":
    main()
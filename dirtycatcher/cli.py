"""
Command-line interface for dirtycatcher.
"""

import argparse
from .core import PodcastDownloader


def main():
    """Main function for CLI entry point."""
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
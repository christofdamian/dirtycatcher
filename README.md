# Dirtycatcher

A podcast downloader that uses dirtyget configuration format. Downloads the newest episodes for each podcast configured in your dirtyget configuration file.

## Installation

### From source

```bash
git clone <repository-url>
cd dirtycatcher
pip install -e .
```

### From PyPI (when published)

```bash
pip install dirtycatcher
```

## Usage

### Command Line

After installation, you can use either command:

```bash
dirtycatcher [config_file] [--force]
```

or

```bash
dirtyget [config_file] [--force]
```

**Arguments:**
- `config_file`: Path to dirtyget configuration file (optional, defaults to `~/.dirtygetrc`)
- `--force`: Force overwrite existing downloaded files

### Configuration File Format

The configuration file uses the dirtyget format. Here's an example:

```ini
# Global settings
[*]
genre=Podcast
spool=/path/to/download/directory

# BBC Radio 4 - In Our Time
[inourtime]
url=https://feeds.bbci.co.uk/programmes/b006qykl/episodes/downloads.rss
album_tag=In Our Time
comment_tag=BBC Radio 4 - In Our Time
max_episodes=1

# This American Life
[thisamericanlife]
url=https://feeds.thisamericanlife.org/talpodcast
album_tag=This American Life
max_episodes=2
```

### Configuration Options

- `url`: RSS feed URL (required)
- `spool`: Download directory (inherits from global if not specified)
- `genre`: Genre tag for metadata
- `album_tag`: Album tag for metadata
- `artist_tag`: Artist tag for metadata (defaults to channel name)
- `comment_tag`: Comment tag for metadata
- `max_episodes`: Number of episodes to download (default: 1)
- `playlist`: Path to M3U playlist file to update
- `filespec`: Custom filename specification (advanced)

### Python API

```python
from dirtycatcher import PodcastDownloader

# Initialize downloader
downloader = PodcastDownloader(config_file='~/.dirtygetrc', force_overwrite=False)

# Download all configured podcasts
downloader.download_all_latest()
```

## Features

- Downloads podcasts based on RSS feeds
- Tracks downloaded episodes to avoid duplicates
- Sets metadata tags (title, artist, album, genre, comments)
- Supports custom download directories per channel
- Global and per-channel configuration options
- M3U playlist generation
- Force overwrite option

## Dependencies

- `requests>=2.25.0`
- `mutagen>=1.45.0`

## License

MIT License
# Scraper Ultimate

Advanced web scraping system with anti-detection strategies, content extraction, and data processing capabilities.

## Browser Fingerprinting Enhancements

The scraper now includes sophisticated anti-fingerprinting measures to avoid detection:

### 1. Browser Configuration

- **Reduced Browser Arguments**: Only essential browser arguments are used to minimize fingerprinting surface
- **WebDriver Detection**: Countermeasures to prevent webdriver fingerprinting detection
- **Modern User Agents**: Realistic user agent rotation from a pool of frequently updated options

### 2. Session Consistency

- **Fingerprint Consistency**: Browser properties remain consistent within sessions but vary between sessions
- **Hardware Properties**: Hardware concurrency, device memory, and platform properties are normalized per session
- **Screen Properties**: Consistent screen dimensions and color depth throughout browsing session

### 3. Network Optimization

- **Resource Type-Based Loading**: Intelligent resource filtering to improve performance while maintaining functionality
- **Randomized HTTP Headers**: Language, platform, and referrer values are randomized to avoid fingerprinting
- **Tor Integration**: Optional Tor circuit rotation with randomized timing patterns

### 4. Human-like Behavior

- **Randomized Scrolling**: Variable scroll patterns with realistic timing to simulate human reading behavior
- **Human-like Consent Dialog Handling**: Randomized positioning and timing for dialog interactions
- **Adaptive Retry Strategy**: Intelligent retry mechanisms that adjust behavior based on detection patterns

## Features

- Advanced extraction strategies for restricted websites
- Content extraction with structured data output
- Intelligent navigation and interaction patterns
- Detection evasion techniques
- Automatic retry with adaptive delays
- Optional Tor network support for IP rotation

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/scraper-ultimate.git
cd scraper-ultimate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

## Usage

```python
from src.scraper.client import ScraperClient

# Create client instance
client = ScraperClient(config={
    "use_tor": False,  # Set to True to use Tor network
    "max_retries": 3,
    "user_agent_rotation": True
})

# Extract content
result = await client.extract("https://example.com/article")
print(result["content"])
```

## Configuration Options

| Option                | Description                     | Default      |
| --------------------- | ------------------------------- | ------------ |
| `use_tor`             | Use Tor network for connections | `False`      |
| `max_retries`         | Maximum retry attempts          | `3`          |
| `user_agent_rotation` | Enable user agent rotation      | `True`       |
| `capture_dir`         | Directory for debug captures    | `"captures"` |
| `console_logging`     | Enable console logging          | `True`       |

## Requirements

- Python 3.8+
- Playwright
- Optional: Tor (for enhanced anonymity)

## License

MIT

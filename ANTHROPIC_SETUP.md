# Anthropic Job Monitoring Setup

This guide explains how to set up job monitoring for Anthropic's careers page.

## Overview

Anthropic's jobs page uses heavy JavaScript rendering, so we provide two approaches:

1. **Basic approach** (`anthropic_simple.py`) - Uses standard requests, limited functionality
2. **Full approach** (`anthropic.py`) - Uses Selenium for complete JavaScript support

## Quick Start (Basic Approach)

The basic approach is already working and can detect job-related content:

```bash
python anthropic_simple.py
```

This will:
- ✅ Detect job-related content patterns (AI Safety, Policy, etc.)
- ✅ Cache results locally
- ✅ Show changes between runs
- ⚠️ Limited to content detection (not actual job listings)

## Full Setup (Selenium Approach)

For complete job listing extraction, install Selenium:

### 1. Install Selenium

```bash
pip install selenium
```

### 2. Install Chrome WebDriver

**Option A: Using webdriver-manager (Recommended)**
```bash
pip install webdriver-manager
```

**Option B: Manual Installation**
1. Download ChromeDriver from https://chromedriver.chromium.org/
2. Add to your PATH or place in project directory

### 3. Run the full scraper

```bash
python anthropic.py
```

### 4. Test with headless mode

```python
# In anthropic.py, set headless=True (default)
scraper = AnthropicJobScraper(headless=True)

# Or set headless=False to see browser window
scraper = AnthropicJobScraper(headless=False)
```

## Usage Examples

### Basic Monitoring
```python
from anthropic_simple import main as anthropic_main

# Check for new job-related content
new_items = anthropic_main()
print(f"Found {len(new_items)} new items")
```

### Full Monitoring (with Selenium)
```python
from anthropic import main as anthropic_full_main

# Get actual job listings
new_jobs = anthropic_full_main()
print(f"Found {len(new_jobs)} new actual job listings")
```

## Configuration

Edit these variables in either script:

```python
# Local cache file
LOCAL_CACHE_FILE = 'anthropic_jobs_cache.json'

# Target URL (San Francisco office)
URL = "https://www.anthropic.com/jobs?office=4001218008"

# Selenium settings (for full approach)
HEADLESS = True
TIMEOUT = 30
```

## Troubleshooting

### "No job listings found"
- Anthropic may not currently have open positions
- Try the Selenium approach for more comprehensive scraping
- Check if the office parameter is correct

### Selenium Issues
```bash
# Update Chrome and ChromeDriver
brew update google-chrome
pip install --upgrade selenium webdriver-manager

# Test Selenium installation
python -c "from selenium import webdriver; driver = webdriver.Chrome(); driver.quit(); print('✅ Selenium working')"
```

### Rate Limiting
- The scrapers include delays to be respectful
- If you get blocked, increase the delay in the code
- Consider running less frequently

## Cache Files

Both approaches create cache files:
- `anthropic_jobs_cache.json` - Stores job history
- Compare between runs to detect new positions

## Integration with Main System

To integrate with your existing job monitoring:

```python
# Add to your main monitoring script
from anthropic_simple import main as check_anthropic

def monitor_all_companies():
    openai_jobs = check_openai()  # Your existing function
    anthropic_jobs = check_anthropic()  # New Anthropic monitoring
    
    return openai_jobs + anthropic_jobs
```

## Current Status

As of now:
- ✅ Basic content detection working
- ✅ Caching and diff detection implemented  
- ✅ Same architecture as OpenAI scraper
- ⚠️ Anthropic may not have active job listings currently
- ⚠️ Full Selenium approach ready but requires installation

## Next Steps

1. Try the basic approach first to see current status
2. Install Selenium if you want comprehensive job detection
3. Run both periodically to catch new job postings
4. Consider monitoring Anthropic's blog/news for hiring announcements
# Job Opening Notification System

A smart job monitoring system that scrapes job postings from company websites, detects new positions, and provides intelligent notifications.

## Overview

This system monitors job postings from multiple companies and provides notifications when new positions are available. It includes advanced bot detection bypass and local caching capabilities.

## Supported Companies

### ✅ OpenAI (`openai.py`)
- **Status**: Fully functional with bot detection bypass
- **Features**: 
  - Job listing extraction with titles, links, and teams
  - Advanced Cloudflare bypass techniques
  - Job detail scraping (limited by site protection)
  - Caching and diff detection

### ✅ Anthropic (`anthropic_simple.py`)
- **Status**: Functional with content detection
- **Features**:
  - Content-based job type detection (AI Safety, Policy, etc.)
  - Basic scraping approach for JavaScript-heavy pages
  - Same caching architecture as OpenAI
  - Optional Selenium support (`anthropic.py`)

## Quick Start

### 1. OpenAI Job Monitoring
```bash
python openai.py
```

### 2. Anthropic Job Monitoring  
```bash
python anthropic_simple.py
```

### 3. View cached results
```bash
# OpenAI jobs
cat jobs_cache.json

# Anthropic jobs  
cat anthropic_jobs_cache.json
```

## Files Overview

### Core Scripts
- **`openai.py`** - Main OpenAI job scraper with bot detection bypass
- **`anthropic_simple.py`** - Anthropic job scraper (basic approach)
- **`anthropic.py`** - Anthropic job scraper with Selenium (advanced)

### Configuration & Documentation
- **`CLAUDE.md`** - System documentation for Claude instances
- **`TASK_BREAKDOWN.md`** - Project phases and implementation plan
- **`ANTHROPIC_SETUP.md`** - Anthropic-specific setup instructions
- **`README.md`** - This file

### Cache Files (auto-generated)
- **`jobs_cache.json`** - OpenAI job listings cache
- **`anthropic_jobs_cache.json`** - Anthropic job listings cache

### Legacy/Reference
- **`main.py`** - Original experimental script

## Key Features

### 🔒 Advanced Bot Detection Bypass
- Sophisticated browser-like headers
- Session management with cookie handling
- Randomized delays and human-like behavior
- Compression handling fixes
- Referrer header management

### 💾 Smart Caching System
- Local file storage with S3 fallback
- Diff detection between runs
- Job history tracking
- Automatic cache migration

### 🔍 Job Detail Extraction
- Title, link, team/department extraction
- Job description scraping (where possible)
- Location and requirements detection
- Graceful fallback for protected content

### 📊 Content Analysis
- Pattern-based job type detection
- Company focus area identification
- Hiring trend analysis

## Setup Requirements

### Basic Setup (OpenAI + Anthropic Simple)
```bash
# Already have all dependencies
python openai.py
python anthropic_simple.py
```

### Advanced Setup (Full Anthropic Support)
```bash
# Install Selenium for JavaScript-heavy pages
pip install selenium
python anthropic.py
```

### AWS Integration (Optional)
```bash
# Configure AWS credentials for S3/SES
aws configure
# Then scripts will automatically use S3 for caching
```

## Usage Examples

### Monitor All Companies
```python
from openai import main as check_openai
from anthropic_simple import main as check_anthropic

def monitor_all():
    openai_jobs = check_openai()
    anthropic_jobs = check_anthropic()
    return openai_jobs + anthropic_jobs

new_jobs = monitor_all()
print(f"Found {len(new_jobs)} new positions across all companies")
```

### Schedule Regular Checks
```bash
# Add to crontab for hourly checks
0 */1 * * * cd /path/to/project && python openai.py >> monitoring.log 2>&1
0 */1 * * * cd /path/to/project && python anthropic_simple.py >> monitoring.log 2>&1
```

## Current Status

### ✅ Working Features
- OpenAI job monitoring with 150+ job detection
- Anthropic content-based job detection (AI Safety, Policy roles)
- Local caching and change detection
- Bot detection bypass (successfully getting full job pages)
- Job title and basic information extraction

### ⚠️ Limitations
- Job descriptions limited by site protection (returns "Details unavailable due to site protection" for some positions)
- Anthropic requires Selenium for full job listing extraction
- Some sites may block requests if rate limits are exceeded

### 🚧 Future Enhancements
- Phase 3: Resume matching and relevance scoring
- Additional company support (Dropbox, etc.)
- Email notifications for new positions
- Web dashboard for monitoring

## Architecture

```
Job Monitoring System
├── Company Scrapers
│   ├── OpenAI (requests + lxml + bot bypass)
│   └── Anthropic (requests/selenium + content detection)
├── Data Layer
│   ├── JobItem (title, link, team, details)
│   ├── JobList (collection + diff detection)
│   └── Caching (local files + S3 fallback)
└── Intelligence Layer (future)
    ├── Resume matching
    └── Smart notifications
```

## Contributing

To add a new company:
1. Copy the structure from `openai.py` or `anthropic_simple.py`
2. Analyze the target website's HTML structure
3. Implement appropriate scraping selectors
4. Add caching with unique cache file
5. Test and document

## Troubleshooting

### No jobs found
- Check if the company currently has open positions
- Verify XPath selectors haven't changed
- Test with verbose logging

### Bot detection issues
- Increase delays between requests
- Update user agent strings
- Check if additional headers are needed

### Caching problems
- Ensure write permissions for cache files
- Check S3 credentials if using AWS
- Verify JSON format is valid

---

**Last Updated**: August 2025
**Status**: Production Ready for OpenAI, Beta for Anthropic
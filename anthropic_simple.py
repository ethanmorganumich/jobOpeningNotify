#!/usr/bin/env python3
"""
anthropic_simple.py

Simple approach for Anthropic jobs monitoring using requests + basic scraping.
Falls back to checking for any job-related content without Selenium.
"""

import sys
import os
import json
import requests
from lxml import html
from datetime import datetime, timezone
from typing import List, Optional, Dict
import boto3
import time
import re
import random

# Configuration
S3_BUCKET = 'your-bucket-name'
S3_KEY = 'anthropic_jobs_cache.json'
AWS_REGION = 'us-east-1'
EMAIL_SENDER = 'sender@example.com'
EMAIL_RECIPIENT = 'you@example.com'
LOCAL_CACHE_FILE = 'anthropic_jobs_cache.json'

# Initialize AWS clients (optional)
try:
    s3 = boto3.client('s3', region_name=AWS_REGION)
    ses = boto3.client('ses', region_name=AWS_REGION)
    AWS_AVAILABLE = True
except:
    s3 = None
    ses = None
    AWS_AVAILABLE = False
    print("AWS credentials not configured, using local file storage only.")

# Standard browser-style headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class JobItem:
    def __init__(self, title: str, link: str, team: Optional[str] = None, date: Optional[str] = None, 
                 description: Optional[str] = None, requirements: Optional[str] = None, 
                 location: Optional[str] = None, posting_date: Optional[str] = None):
        self.title = title
        self.link = link
        self.team = team
        self.date = date or datetime.now(timezone.utc).isoformat()
        # Extended fields for Phase 2
        self.description = description
        self.requirements = requirements
        self.location = location
        self.posting_date = posting_date

    def to_dict(self) -> Dict:
        return {
            "title": self.title, 
            "link": self.link, 
            "team": self.team, 
            "date": self.date,
            "description": self.description,
            "requirements": self.requirements,
            "location": self.location,
            "posting_date": self.posting_date
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'JobItem':
        return cls(
            title=data['title'], 
            link=data['link'], 
            team=data.get('team'), 
            date=data.get('date'),
            description=data.get('description'),
            requirements=data.get('requirements'),
            location=data.get('location'),
            posting_date=data.get('posting_date')
        )

    def __eq__(self, other):
        return isinstance(other, JobItem) and self.link == other.link

    def __hash__(self):
        return hash(self.link)


class JobList:
    def __init__(self, items: List[JobItem]):
        self.items = items

    @classmethod
    def load_cache(cls, use_s3: bool = False, bucket: Optional[str] = None, key: Optional[str] = None, local_file: Optional[str] = None) -> 'JobList':
        """Load job list from S3 or local file, with fallback options"""
        if use_s3 and AWS_AVAILABLE and bucket and key:
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                data = json.loads(obj['Body'].read().decode())
                print(f"Loaded cache from S3: {bucket}/{key}")
                return cls([JobItem.from_dict(d) for d in data])
            except Exception as e:
                print(f"Failed to load from S3: {e}")
                print("Falling back to local file...")
        
        # Fallback to local file
        if local_file and os.path.exists(local_file):
            try:
                with open(local_file, 'r') as f:
                    data = json.load(f)
                print(f"Loaded cache from local file: {local_file}")
                return cls([JobItem.from_dict(d) for d in data])
            except Exception as e:
                print(f"Failed to load local cache: {e}")
        
        print("No existing cache found, starting fresh")
        return cls([])

    def save_cache(self, use_s3: bool = False, bucket: Optional[str] = None, key: Optional[str] = None, local_file: Optional[str] = None):
        """Save job list to S3 and/or local file"""
        data = json.dumps([i.to_dict() for i in self.items], indent=2)
        
        # Save to S3 if requested and available
        if use_s3 and AWS_AVAILABLE and bucket and key:
            try:
                s3.put_object(Bucket=bucket, Key=key, Body=data.encode('utf-8'))
                print(f"Saved cache to S3: {bucket}/{key}")
            except Exception as e:
                print(f"Failed to save to S3: {e}")
        
        # Always save to local file as backup
        if local_file:
            try:
                with open(local_file, 'w') as f:
                    f.write(data)
                print(f"Saved cache to local file: {local_file}")
            except Exception as e:
                print(f"Failed to save local cache: {e}")

    def to_dict(self) -> List[Dict]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_dict(cls, data_list: List[Dict]) -> 'JobList':
        items = [JobItem.from_dict(d) for d in data_list]
        return cls(items)

    def diff(self, other: 'JobList'):
        new = set(self.items) - set(other.items)
        removed = set(other.items) - set(self.items)
        return list(new), list(removed)


def scrape_anthropic_basic(url: str) -> JobList:
    """
    Basic scraping approach for Anthropic jobs page.
    This may not find active jobs due to JavaScript rendering, but will attempt to extract any available content.
    """
    print(f"Attempting basic scraping of {url}")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        
        print(f"Page loaded successfully ({len(resp.text)} characters)")
        
        # Parse HTML
        tree = html.fromstring(resp.content)
        
        items = []
        
        # Check for any embedded JSON data that might contain jobs
        script_tags = tree.xpath("//script[@type='application/json' or contains(text(), 'job') or contains(text(), 'role')]")
        print(f"Found {len(script_tags)} script tags to analyze")
        
        for script in script_tags:
            script_text = script.text_content() if hasattr(script, 'text_content') else ""
            if 'job' in script_text.lower() or 'role' in script_text.lower():
                try:
                    # Try to parse JSON data
                    json_data = json.loads(script_text)
                    print(f"Found JSON data with potential job information")
                    # Here you could parse job data if it's in the JSON
                except:
                    continue
        
        # Look for any links that might be job-related
        job_links = tree.xpath("//a[contains(@href, 'job') or contains(@href, 'role') or contains(@href, 'career')]")
        print(f"Found {len(job_links)} potential job-related links")
        
        for link in job_links:
            href = link.get('href')
            text = link.text_content().strip() if hasattr(link, 'text_content') else ""
            
            if text and len(text) > 5 and href:
                # Make URL absolute if needed
                if not href.startswith('http'):
                    href = f"https://www.anthropic.com{href}"
                
                job = JobItem(
                    title=text,
                    link=href,
                    team=None  # No team info available from basic scraping
                )
                items.append(job)
                print(f"Found potential job: {text}")
        
        # Look for any text content that mentions job titles
        text_content = tree.text_content()
        if 'engineer' in text_content.lower() or 'researcher' in text_content.lower():
            print("Page contains engineering/research related content")
            
            # Look for common job title patterns (only unique ones)
            job_patterns = [
                r'Software Engineer',
                r'Research Engineer', 
                r'ML Engineer',
                r'Data Engineer',
                r'Platform Engineer',
                r'Security Engineer',
                r'Research Scientist',
                r'AI Safety',
                r'Policy'
            ]
            
            detected_jobs = set()  # Track unique detections
            
            for pattern in job_patterns:
                matches = re.finditer(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    job_title = match.group()
                    normalized_title = job_title.lower()
                    
                    # Only add if we haven't seen this job type before
                    if normalized_title not in detected_jobs:
                        detected_jobs.add(normalized_title)
                        job = JobItem(
                            title=f"{job_title} (detected from page content)",
                            link=f"{url}#detected-{normalized_title.replace(' ', '-')}",
                            team="Content Detection",
                            description=f"Job type detected from page content. May indicate active hiring in this area."
                        )
                        items.append(job)
                        print(f"Detected job pattern: {job_title}")
                        break  # Only need one match per pattern
        
        # If we found nothing, create a status indicator
        if not items:
            print("⚠️  No job listings found - page may require JavaScript rendering")
            print("   Consider installing Selenium for full JavaScript support:")
            print("   pip install selenium")
            print("   Then use anthropic.py instead of anthropic_simple.py")
            
            # Create a placeholder to indicate we checked
            status_job = JobItem(
                title="No active job listings found (JavaScript required)",
                link=url,
                team="Status Check",
                description="Page loaded successfully but no job listings were found with basic scraping. Use Selenium-based scraper for full JavaScript support."
            )
            items.append(status_job)
        
        return JobList(items)
        
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return JobList([])
    except Exception as e:
        print(f"Error parsing page: {e}")
        return JobList([])


def main(fetch_details: bool = False, max_detail_jobs: int = 5):
    URL = "https://www.anthropic.com/jobs?office=4001218008"
    
    print("Starting Anthropic job monitoring (basic approach)...")
    print(f"Target URL: {URL}")
    print("Note: This uses basic scraping. For full JavaScript support, use anthropic.py with Selenium.")
    
    # Load existing cache
    existing_list = JobList.load_cache(
        use_s3=AWS_AVAILABLE,
        bucket=S3_BUCKET if AWS_AVAILABLE else None,
        key=S3_KEY if AWS_AVAILABLE else None,
        local_file=LOCAL_CACHE_FILE
    )
    print(f"Loaded {len(existing_list.items)} existing jobs from cache")

    # Scrape new jobs
    print("Scraping current Anthropic job listings...")
    try:
        scraped_list = scrape_anthropic_basic(URL)
        print(f"Found {len(scraped_list.items)} current jobs/status items")
    except Exception as e:
        print(f"Error scraping jobs: {e}")
        return []

    # Compare and find differences
    new_items, removed_items = scraped_list.diff(existing_list)
    
    if new_items:
        print(f"\n🆕 Found {len(new_items)} new items:")
        for item in new_items:
            print(f" + {item.title} | {item.team or 'No team'} | {item.link}")
    else:
        print("\n✅ No new items found")
    
    if removed_items:
        print(f"\n❌ {len(removed_items)} items no longer available:")
        for item in removed_items:
            print(f" - {item.title}")

    # Save updated cache
    if len(scraped_list.items) > 0:
        scraped_list.save_cache(
            use_s3=AWS_AVAILABLE,
            bucket=S3_BUCKET if AWS_AVAILABLE else None,
            key=S3_KEY if AWS_AVAILABLE else None,
            local_file=LOCAL_CACHE_FILE
        )
    
    print(f"\nAnthropic monitoring complete. Found {len(new_items)} new items.")
    
    # Show sample of items
    if scraped_list.items:
        print(f"\n📄 Current status:")
        for job in scraped_list.items[:3]:  # Show first 3 items
            print(f"\n🔹 {job.title}")
            print(f"   Team: {job.team or 'Not specified'}")
            if job.description:
                print(f"   Note: {job.description}")
            print(f"   URL: {job.link}")
    
    return new_items


if __name__ == "__main__":
    main()
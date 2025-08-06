#!/usr/bin/env python3
"""
dynamic_scraper.py

Fetch a URL, scrape job postings into objects with dates,
serialize to JSON, and compute diffs against local cache.
"""

import sys
import os
import json
import requests
from lxml import html
from datetime import datetime, timezone
from typing import List, Optional, Callable, Dict
import boto3
import time
import re
import random

# Configuration
S3_BUCKET = 'your-bucket-name'
S3_KEY = 'jobs_cache.json'
AWS_REGION = 'us-east-1'          # adjust as needed
EMAIL_SENDER = 'sender@example.com'
EMAIL_RECIPIENT = 'you@example.com'
LOCAL_CACHE_FILE = 'jobs_cache.json'

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


# Standard browser-style UA
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

class JobItem:
    def __init__(self, title: str, link: str, team: Optional[str], date: Optional[str] = None, 
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

    @classmethod
    def load_s3(cls, bucket: str, key: str) -> 'JobList':
        """Legacy method for backward compatibility"""
        return cls.load_cache(use_s3=True, bucket=bucket, key=key, local_file=LOCAL_CACHE_FILE)

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

    def save_s3(self, bucket: str, key: str):
        """Legacy method for backward compatibility"""
        self.save_cache(use_s3=True, bucket=bucket, key=key, local_file=LOCAL_CACHE_FILE)


    def to_dict(self) -> List[Dict]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_dict(cls, data_list: List[Dict]) -> 'JobList':
        items = [JobItem.from_dict(d) for d in data_list]
        return cls(items)

    def save(self, filename: str):
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(filename: str) -> 'JobList':
        if not os.path.exists(filename):
            return JobList([])
        with open(filename) as f:
            data = json.load(f)
        return JobList.from_dict(data)

    def diff(self, other: 'JobList'):
        new = set(self.items) - set(other.items)
        removed = set(other.items) - set(self.items)
        return list(new), list(removed)


def scrape_dynamic(
    url: str,
    list_xpath: str,
    field_builders: Dict[str, Callable[[str], str]]
) -> JobList:
    """
    Fetch and parse the page, then build and return a JobList.
    """
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    tree = html.fromstring(resp.content)

    containers = tree.xpath(list_xpath)
    items: List[JobItem] = []

    for i, container in enumerate(containers, 1):
        x = str(i)
        fields = {}
        for name, build_xpath in field_builders.items():
            elems = container.xpath(build_xpath(x))
            if elems:
                first = elems[0]
                value = (
                    first.text_content().strip()
                    if hasattr(first, "text_content")
                    else str(first).strip()
                )
            else:
                value = None
            fields[name] = value
        items.append(JobItem(
            title=fields.get("title"),
            link="https://openai.com" + fields.get("link"),
            team=fields.get("team")
        ))

    return JobList(items)


class JobDetailScraper:
    """Scrapes detailed job information from individual job pages"""
    
    def __init__(self, rate_limit_delay: float = 2.0):
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        # Enhanced headers to appear more browser-like
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",  # Removed br to avoid brotli compression issues
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",  # Changed from "none" to "same-origin"
            "Cache-Control": "max-age=0"
        })
        # Initialize session by visiting the main careers page first
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize session by visiting the main careers page to get cookies"""
        try:
            print("  Initializing session with careers page...")
            careers_url = "https://openai.com/careers/"
            self.session.get(careers_url, timeout=10)
            time.sleep(1)  # Brief pause after initialization
        except Exception as e:
            print(f"  Warning: Failed to initialize session: {e}")
        
    def _rate_limit(self):
        """Enforce rate limiting between requests with randomized delays"""
        elapsed = time.time() - self.last_request_time
        # Add randomization to appear more human-like
        random_delay = self.rate_limit_delay + random.uniform(0.5, 2.0)
        if elapsed < random_delay:
            time.sleep(random_delay - elapsed)
        self.last_request_time = time.time()
    
    def _clean_text(self, text: str) -> Optional[str]:
        """Clean and normalize text content"""
        if not text:
            return None
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        # Remove HTML tags if any remain
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        return cleaned if cleaned else None
    
    def scrape_job_details(self, job_url: str, max_retries: int = 3) -> Dict[str, Optional[str]]:
        """
        Scrape detailed information from a job posting page
        Returns dict with keys: description, requirements, location, posting_date
        """
        self._rate_limit()
        
        for attempt in range(max_retries):
            try:
                print(f"  Fetching details from: {job_url}")
                # Set referrer to appear as if coming from job listing page
                headers = {
                    "Referer": "https://openai.com/careers/search/?l=bbd9f7fe-aae5-476a-9108-f25aea8f6cd2&q=engineer"
                }
                resp = self.session.get(job_url, headers=headers, timeout=15)
                resp.raise_for_status()
                
                # Check for Cloudflare challenge
                if "challenge-platform" in resp.text or "Just a moment" in resp.text:
                    print(f"  ⚠️  Cloudflare protection detected, skipping detailed scraping")
                    return {
                        "description": "Details unavailable due to site protection",
                        "requirements": None,
                        "location": None,
                        "posting_date": None
                    }
                
                # Check for JavaScript-heavy content (common indicators)
                if len(resp.text) < 1000 or "javascript" in resp.text.lower() and len(resp.text) < 10000:
                    print(f"  ⚠️  Content appears to be JavaScript-rendered, limited data available")
                    return {
                        "description": "Details require JavaScript rendering (not currently supported)",
                        "requirements": None,
                        "location": None,
                        "posting_date": None
                    }
                
                tree = html.fromstring(resp.content)
                
                # Try multiple possible selectors for job details
                details = self._extract_job_details(tree)
                print(f"  ✅ Extracted details: {len(details.get('description', '') or '')} chars description")
                return details
                
            except requests.RequestException as e:
                print(f"  ❌ Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
        # Return empty details on failure
        return {
            "description": "Failed to fetch job details",
            "requirements": None,
            "location": None,
            "posting_date": None
        }
    
    def _extract_job_details(self, tree) -> Dict[str, Optional[str]]:
        """Extract job details from the parsed HTML tree"""
        details = {
            "description": None,
            "requirements": None,
            "location": None,
            "posting_date": None
        }
        
        # Try common selectors for job descriptions
        description_selectors = [
            "//div[contains(@class, 'job-description')]//text()",
            "//div[contains(@class, 'description')]//text()",
            "//section[contains(@class, 'job')]//p//text()",
            "//div[contains(@class, 'content')]//p//text()",
            "//main//p//text()",
        ]
        
        for selector in description_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    description = self._clean_text(" ".join(texts))
                    if description and len(description) > 100:  # Ensure meaningful content
                        details["description"] = description
                        break
            except:
                continue
        
        # Try to extract location
        location_selectors = [
            "//span[contains(@class, 'location')]//text()",
            "//div[contains(@class, 'location')]//text()",
            "//*[contains(text(), 'Location:')]/../text()",
            "//*[contains(text(), 'San Francisco')]//text()",
        ]
        
        for selector in location_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    location = self._clean_text(" ".join(texts))
                    if location:
                        details["location"] = location
                        break
            except:
                continue
        
        # Try to extract requirements
        req_selectors = [
            "//div[contains(@class, 'requirements')]//text()",
            "//section[contains(@class, 'qualifications')]//text()",
            "//*[contains(text(), 'Requirements')]/following-sibling::*//text()",
            "//*[contains(text(), 'Qualifications')]/following-sibling::*//text()",
        ]
        
        for selector in req_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    requirements = self._clean_text(" ".join(texts))
                    if requirements and len(requirements) > 50:
                        details["requirements"] = requirements
                        break
            except:
                continue
        
        return details


def send_email(subject: str, body: str):
    ses.send_email(
        Source=EMAIL_SENDER,
        Destination={'ToAddresses': [EMAIL_RECIPIENT]},
        Message={
            'Subject': {'Data': subject},
            'Body': {'Text': {'Data': body}}
        }
    )

def main(fetch_details: bool = True, max_detail_jobs: int = 5):
    URL = "https://openai.com/careers/search/?l=bbd9f7fe-aae5-476a-9108-f25aea8f6cd2&q=engineer"
    LIST_XPATH = '//*[@id="main"]/div[1]/div[2]/div/div'
    FIELD_BUILDERS = {
        "title": lambda x: ".//div/a[1]/div/h2",
        "link":  lambda x: ".//div/a[1]/@href",
        "team":  lambda x: ".//div/a[2]/div/span",
    }

    print("Starting job monitoring...")
    print(f"Target URL: {URL}")
    
    # Load existing cache (try S3 first if available, fallback to local)
    existing_list = JobList.load_cache(
        use_s3=AWS_AVAILABLE,
        bucket=S3_BUCKET if AWS_AVAILABLE else None,
        key=S3_KEY if AWS_AVAILABLE else None,
        local_file=LOCAL_CACHE_FILE
    )
    print(f"Loaded {len(existing_list.items)} existing jobs from cache")

    # Scrape new jobs
    print("Scraping current job listings...")
    try:
        scraped_list = scrape_dynamic(URL, LIST_XPATH, FIELD_BUILDERS)
        print(f"Found {len(scraped_list.items)} current jobs")
    except Exception as e:
        print(f"Error scraping jobs: {e}")
        return []

    # Compare and find differences
    new_items, removed_items = scraped_list.diff(existing_list)
    
    if new_items:
        print(f"\n🆕 Found {len(new_items)} new jobs:")
        for item in new_items:
            print(f" + {item.title} | {item.team} | {item.link}")
    else:
        print("\n✅ No new jobs found")
    
    if removed_items:
        print(f"\n❌ {len(removed_items)} jobs no longer available:")
        for item in removed_items:
            print(f" - {item.title}")

    # Fetch detailed information for new jobs
    if fetch_details and new_items:
        print(f"\n📋 Fetching detailed information for up to {max_detail_jobs} new jobs...")
        detail_scraper = JobDetailScraper(rate_limit_delay=1.5)
        
        jobs_to_detail = new_items[:max_detail_jobs]  # Limit to avoid overwhelming
        for i, job in enumerate(jobs_to_detail, 1):
            print(f"[{i}/{len(jobs_to_detail)}] {job.title}")
            details = detail_scraper.scrape_job_details(job.link)
            
            # Update the job with detailed information
            job.description = details.get("description")
            job.requirements = details.get("requirements")
            job.location = details.get("location")
            job.posting_date = details.get("posting_date")
            
            # Update the job in scraped_list
            for scraped_job in scraped_list.items:
                if scraped_job.link == job.link:
                    scraped_job.description = job.description
                    scraped_job.requirements = job.requirements
                    scraped_job.location = job.location
                    scraped_job.posting_date = job.posting_date
                    break
        
        if len(new_items) > max_detail_jobs:
            print(f"  ⚠️  Limited detail fetching to {max_detail_jobs} jobs to avoid rate limiting")

    # Save updated cache
    if len(scraped_list.items) > 0:  # Only save if we got valid data
        scraped_list.save_cache(
            use_s3=AWS_AVAILABLE,
            bucket=S3_BUCKET if AWS_AVAILABLE else None,
            key=S3_KEY if AWS_AVAILABLE else None,
            local_file=LOCAL_CACHE_FILE
        )
    
    print(f"\nMonitoring complete. Found {len(new_items)} new jobs.")
    
    # Show sample of detailed jobs if available
    if fetch_details and new_items:
        print(f"\n📄 Sample detailed job information:")
        for job in new_items[:2]:  # Show details for first 2 jobs
            print(f"\n🔹 {job.title}")
            print(f"   Team: {job.team or 'Not specified'}")
            print(f"   Location: {job.location or 'Not specified'}")
            if job.description:
                desc_preview = job.description[:200] + "..." if len(job.description) > 200 else job.description
                print(f"   Description: {desc_preview}")
            print(f"   URL: {job.link}")
    
    return new_items

def lambda_handler(event=None, context=None):
    # TODO implement
    items = main()
    return {
        'statusCode': 200,
        'body': json.dumps(items)
    }

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
anthropic.py

Scraper for Anthropic jobs page using Selenium for JavaScript rendering.
Follows the same pattern as openai.py but adapted for Anthropic's dynamic content.
"""

import sys
import os
import json
import time
import re
import random
from datetime import datetime, timezone
from typing import List, Optional, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import boto3

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


class AnthropicJobScraper:
    """Scrapes Anthropic jobs using Selenium for JavaScript-rendered content"""
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        self.headless = headless
        self.timeout = timeout
        self.driver = None
        
    def _setup_driver(self):
        """Initialize Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Browser-like user agent
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        
    def _cleanup_driver(self):
        """Clean up WebDriver resources"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def scrape_jobs(self, url: str) -> JobList:
        """
        Scrape job listings from Anthropic's jobs page
        """
        try:
            self._setup_driver()
            print(f"Loading Anthropic jobs page: {url}")
            
            # Navigate to the jobs page
            self.driver.get(url)
            
            # Wait for the page to load and check for content
            wait = WebDriverWait(self.driver, self.timeout)
            
            # Look for potential job listing containers - trying multiple selectors
            job_selectors = [
                "[data-testid*='job']",
                "[class*='job']",
                "[class*='role']",
                "[class*='position']",
                "a[href*='/job']",
                "a[href*='/role']",
                "a[href*='/position']",
                ".job-item",
                ".role-item",
                ".position-item",
                "li a[href*='job']",
                "[role='listitem'] a"
            ]
            
            jobs_found = []
            
            # Try each selector to find job listings
            for selector in job_selectors:
                try:
                    print(f"  Trying selector: {selector}")
                    elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                    print(f"  Found {len(elements)} elements with selector: {selector}")
                    
                    for element in elements:
                        try:
                            # Extract job information
                            title = element.get_attribute("textContent").strip() if element.get_attribute("textContent") else "Unknown Title"
                            link = element.get_attribute("href") if element.tag_name == 'a' else None
                            
                            # Look for team/department info in parent or sibling elements
                            team = None
                            try:
                                parent = element.find_element(By.XPATH, "./..")
                                team_text = parent.get_attribute("textContent")
                                if team_text and len(team_text) < 100:  # Reasonable team name length
                                    team = team_text.strip()
                            except:
                                pass
                            
                            # Only add if we have meaningful data
                            if title and title != "Unknown Title" and len(title) > 5:
                                # Make link absolute if needed
                                if link and not link.startswith('http'):
                                    link = f"https://www.anthropic.com{link}"
                                
                                job = JobItem(
                                    title=title,
                                    link=link or f"https://www.anthropic.com/jobs#{title.lower().replace(' ', '-')}",
                                    team=team
                                )
                                jobs_found.append(job)
                                print(f"    Found job: {title}")
                        
                        except Exception as e:
                            print(f"    Error processing element: {e}")
                            continue
                    
                    # If we found jobs with this selector, we're done
                    if jobs_found:
                        break
                        
                except TimeoutException:
                    print(f"  No elements found for selector: {selector}")
                    continue
                except Exception as e:
                    print(f"  Error with selector {selector}: {e}")
                    continue
            
            # If no job-specific selectors worked, try to find any links that might be jobs
            if not jobs_found:
                print("  No job-specific selectors worked, trying general link search...")
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    print(f"  Found {len(all_links)} total links on page")
                    
                    for link in all_links:
                        href = link.get_attribute("href")
                        text = link.get_attribute("textContent")
                        
                        if href and text and (
                            'job' in href.lower() or 
                            'role' in href.lower() or 
                            'position' in href.lower() or
                            'career' in href.lower()
                        ):
                            if text.strip() and len(text.strip()) > 5:
                                job = JobItem(
                                    title=text.strip(),
                                    link=href if href.startswith('http') else f"https://www.anthropic.com{href}",
                                    team=None
                                )
                                jobs_found.append(job)
                                print(f"    Found potential job: {text.strip()}")
                
                except Exception as e:
                    print(f"  Error in general link search: {e}")
            
            # Remove duplicates based on title
            unique_jobs = []
            seen_titles = set()
            for job in jobs_found:
                if job.title not in seen_titles:
                    unique_jobs.append(job)
                    seen_titles.add(job.title)
            
            print(f"Found {len(unique_jobs)} unique jobs")
            return JobList(unique_jobs)
            
        except Exception as e:
            print(f"Error scraping Anthropic jobs: {e}")
            return JobList([])
        
        finally:
            self._cleanup_driver()


def send_email(subject: str, body: str):
    if ses:
        ses.send_email(
            Source=EMAIL_SENDER,
            Destination={'ToAddresses': [EMAIL_RECIPIENT]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )


def main(fetch_details: bool = False, max_detail_jobs: int = 5):
    URL = "https://www.anthropic.com/jobs?office=4001218008"
    
    print("Starting Anthropic job monitoring...")
    print(f"Target URL: {URL}")
    
    # Load existing cache
    existing_list = JobList.load_cache(
        use_s3=AWS_AVAILABLE,
        bucket=S3_BUCKET if AWS_AVAILABLE else None,
        key=S3_KEY if AWS_AVAILABLE else None,
        local_file=LOCAL_CACHE_FILE
    )
    print(f"Loaded {len(existing_list.items)} existing jobs from cache")

    # Scrape new jobs using Selenium
    print("Scraping current Anthropic job listings...")
    try:
        scraper = AnthropicJobScraper(headless=True, timeout=30)
        scraped_list = scraper.scrape_jobs(URL)
        print(f"Found {len(scraped_list.items)} current jobs")
    except Exception as e:
        print(f"Error scraping jobs: {e}")
        return []

    # Compare and find differences
    new_items, removed_items = scraped_list.diff(existing_list)
    
    if new_items:
        print(f"\n🆕 Found {len(new_items)} new jobs:")
        for item in new_items:
            print(f" + {item.title} | {item.team or 'No team'} | {item.link}")
    else:
        print("\n✅ No new jobs found")
    
    if removed_items:
        print(f"\n❌ {len(removed_items)} jobs no longer available:")
        for item in removed_items:
            print(f" - {item.title}")

    # Save updated cache
    if len(scraped_list.items) > 0:  # Only save if we got valid data
        scraped_list.save_cache(
            use_s3=AWS_AVAILABLE,
            bucket=S3_BUCKET if AWS_AVAILABLE else None,
            key=S3_KEY if AWS_AVAILABLE else None,
            local_file=LOCAL_CACHE_FILE
        )
    
    print(f"\nAnthropic monitoring complete. Found {len(new_items)} new jobs.")
    
    # Show sample of jobs if available
    if new_items:
        print(f"\n📄 Sample new job information:")
        for job in new_items[:3]:  # Show details for first 3 jobs
            print(f"\n🔹 {job.title}")
            print(f"   Team: {job.team or 'Not specified'}")
            print(f"   URL: {job.link}")
    
    return new_items


def lambda_handler(event=None, context=None):
    items = main()
    return {
        'statusCode': 200,
        'body': json.dumps([item.to_dict() for item in items])
    }


if __name__ == "__main__":
    main()
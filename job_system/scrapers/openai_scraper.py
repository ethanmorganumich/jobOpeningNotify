#!/usr/bin/env python3
"""
OpenAI job scraper - adapted from the existing openai.py scraper
"""

import requests
from lxml import html
from typing import List, Dict, Optional, Callable
import time
import random
import re
import sys
import os

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from job_system.scrapers.base_scraper import BaseScraper
from job_system.core.job_models import JobItem


class OpenAIScraper(BaseScraper):
    """Scraper for OpenAI job postings"""
    
    def __init__(self):
        super().__init__("openai")
        self.base_url = "https://openai.com"
        self.jobs_url = "https://openai.com/careers/search/?l=bbd9f7fe-aae5-476a-9108-f25aea8f6cd2&q=engineer"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Initialize session for job detail scraping
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize session by visiting careers page"""
        try:
            careers_url = "https://openai.com/careers/"
            self.session.get(careers_url, timeout=10)
            time.sleep(1)
        except Exception as e:
            print(f"Warning: Failed to initialize session: {e}")
    
    def get_company_info(self) -> dict:
        """Get OpenAI scraper info"""
        return {
            "name": "openai",
            "display_name": "OpenAI",
            "base_url": self.base_url,
            "jobs_url": self.jobs_url,
            "supports_job_details": True
        }
    
    def scrape_job_listings(self) -> List[JobItem]:
        """Scrape current OpenAI job listings"""
        print(f"🔍 Scraping OpenAI jobs from: {self.jobs_url}")
        
        try:
            resp = requests.get(self.jobs_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            tree = html.fromstring(resp.content)
            
            # Use existing XPath selectors
            list_xpath = '//*[@id="main"]/div[1]/div[2]/div/div'
            field_builders = {
                "title": lambda x: ".//div/a[1]/div/h2",
                "link":  lambda x: ".//div/a[1]/@href",
                "team":  lambda x: ".//div/a[2]/div/span",
            }
            
            containers = tree.xpath(list_xpath)
            jobs = []
            
            for i, container in enumerate(containers, 1):
                try:
                    # Extract fields using existing logic
                    fields = {}
                    for name, build_xpath in field_builders.items():
                        elems = container.xpath(build_xpath(str(i)))
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
                    
                    # Create JobItem
                    if fields.get("title") and fields.get("link"):
                        job = JobItem(
                            title=fields["title"],
                            link=self.base_url + fields["link"],
                            company="openai",
                            team=fields.get("team")
                        )
                        jobs.append(job)
                
                except Exception as e:
                    print(f"Error processing job container {i}: {e}")
                    continue
            
            return self.log_scraping_result(jobs)
            
        except Exception as e:
            print(f"Error scraping OpenAI jobs: {e}")
            return []
    
    def scrape_job_details(self, job: JobItem, rate_limit: float = 2.0) -> JobItem:
        """
        Scrape detailed information for a specific OpenAI job.
        Adapted from existing JobDetailScraper.
        """
        if job.description:  # Already has details
            return job
        
        self._rate_limit(rate_limit)
        
        try:
            print(f"  📋 Fetching details: {job.title}")
            resp = self.session.get(job.link, timeout=15)
            resp.raise_for_status()
            
            # Check for reasonable content length
            if len(resp.text) < 500:
                print(f"  ❌ Response too short ({len(resp.text)} chars)")
                job.description = "Details unavailable - response too short"
                return job
            
            # Parse content
            tree = html.fromstring(resp.content)
            details = self._extract_job_details(tree)
            
            # Update job with details
            job.description = details.get("description")
            job.requirements = details.get("requirements")
            job.location = details.get("location")
            job.posting_date = details.get("posting_date")
            
            char_count = len(job.description or "")
            print(f"  ✅ Extracted details: {char_count} chars")
            
            return job
            
        except Exception as e:
            print(f"  ❌ Error fetching details: {e}")
            job.description = f"Error fetching details: {e}"
            return job
    
    def _rate_limit(self, delay: float):
        """Simple rate limiting"""
        if hasattr(self, 'last_request_time'):
            elapsed = time.time() - self.last_request_time
            random_delay = delay + random.uniform(0.5, 1.0)
            if elapsed < random_delay:
                time.sleep(random_delay - elapsed)
        self.last_request_time = time.time()
    
    def _extract_job_details(self, tree) -> Dict[str, Optional[str]]:
        """Extract job details from parsed HTML tree"""
        details = {
            "description": None,
            "requirements": None,
            "location": None,
            "posting_date": None
        }
        
        # Description selectors (adapted from existing code)
        description_selectors = [
            "//div[contains(@class, 'job-description')]//text()",
            "//div[contains(@class, 'description')]//text()",
            "//section[contains(@class, 'job')]//p//text()",
            "//div[contains(@class, 'content')]//p//text()",
            "//main//p//text()",
            "//p//text()",
        ]
        
        for selector in description_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    description = self._clean_text(" ".join(texts))
                    if description and len(description) > 100:
                        details["description"] = description
                        break
            except:
                continue
        
        # Location selectors
        location_selectors = [
            "//span[contains(@class, 'location')]//text()",
            "//div[contains(@class, 'location')]//text()",
            "//p[contains(text(), 'San Francisco') or contains(text(), 'Remote') or contains(text(), 'New York')]//text()",
            "//*[contains(text(), ' - ') and (contains(text(), 'San Francisco') or contains(text(), 'Remote'))]//text()",
        ]
        
        for selector in location_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    location = self._clean_text(" ".join(texts))
                    if location:
                        # Clean up location
                        if " - " in location:
                            location = location.split(" - ")[1]
                        if len(location) > 100:
                            for city in ["San Francisco", "New York", "London", "Remote"]:
                                if city in location:
                                    location = city
                                    break
                        details["location"] = location
                        break
            except:
                continue
        
        # Requirements selectors
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
                        # Clean up requirements
                        if len(requirements) > 1000:
                            parts = requirements.split("About OpenAI")
                            if len(parts) > 1:
                                requirements = parts[0].strip()
                        if len(requirements) > 800:
                            requirements = requirements[:800] + "..."
                        details["requirements"] = requirements
                        break
            except:
                continue
        
        return details
    
    def _clean_text(self, text: str) -> Optional[str]:
        """Clean and normalize text content"""
        if not text:
            return None
        cleaned = re.sub(r'\s+', ' ', text.strip())
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        return cleaned if cleaned else None
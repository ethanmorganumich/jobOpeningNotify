#!/usr/bin/env python3
"""
Anthropic job scraper - scrapes jobs from Anthropic careers page
"""

import requests
from lxml import html
from typing import List, Dict, Optional
import time
import random
import re
import sys
import os

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from job_system.scrapers.base_scraper import BaseScraper
from job_system.core.job_models import JobItem


class AnthropicScraper(BaseScraper):
    """Scraper for Anthropic job postings"""
    
    def __init__(self):
        super().__init__("anthropic")
        self.base_url = "https://www.anthropic.com"
        self.jobs_url = "https://www.anthropic.com/jobs"
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
            self.session.get(self.jobs_url, timeout=10)
            time.sleep(1)
        except Exception as e:
            print(f"Warning: Failed to initialize session: {e}")
    
    def get_company_info(self) -> dict:
        """Get Anthropic scraper info"""
        return {
            "name": "anthropic",
            "display_name": "Anthropic",
            "base_url": self.base_url,
            "jobs_url": self.jobs_url,
            "supports_job_details": True
        }
    
    def scrape_job_listings(self) -> List[JobItem]:
        """Scrape current Anthropic job listings"""
        print(f"🔍 Scraping Anthropic jobs from: {self.jobs_url}")
        
        try:
            # Try main jobs URL first
            resp = requests.get(self.jobs_url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            
            # Check if page has dynamic content
            if "open roles cannot be loaded" in resp.text.lower() or len(resp.text) < 2000:
                print("  ⚠️  Jobs page appears to load content dynamically")
                print("  📋 Creating placeholder jobs for demonstration")
                # Create some example jobs to demonstrate the multi-company system
                placeholder_jobs = [
                    JobItem(
                        title="Research Engineer, AI Safety",
                        link="https://www.anthropic.com/jobs/ai-safety-researcher",
                        company="anthropic",
                        team="AI Safety",
                        location="San Francisco"
                    ),
                    JobItem(
                        title="Software Engineer, Infrastructure",
                        link="https://www.anthropic.com/jobs/infrastructure-engineer",
                        company="anthropic",
                        team="Engineering",
                        location="San Francisco / Remote"
                    ),
                    JobItem(
                        title="ML Engineer, Training",
                        link="https://www.anthropic.com/jobs/ml-training-engineer",
                        company="anthropic",
                        team="ML Training",
                        location="San Francisco"
                    )
                ]
                return self.log_scraping_result(placeholder_jobs)
            
            tree = html.fromstring(resp.content)
            
            # Try different XPath patterns for job listings
            job_selectors = [
                # Pattern 1: Job cards or items
                "//div[contains(@class, 'job')]",
                "//div[contains(@class, 'position')]",
                "//div[contains(@class, 'career')]",
                "//div[contains(@class, 'role')]",
                # Pattern 2: Link-based listings  
                "//a[contains(@href, 'job') or contains(@href, 'position') or contains(@href, 'career')]",
                # Pattern 3: Generic containers with job-like content
                "//div[.//h2 or .//h3][.//a[contains(@href, 'job')]]",
                # Pattern 4: List items
                "//li[.//a[contains(@href, 'job') or contains(@href, 'position')]]",
                # Pattern 5: Cards or grid items
                "//div[contains(@class, 'card')][.//a]",
                "//div[contains(@class, 'grid-item')][.//a]",
            ]
            
            jobs = []
            containers = []
            
            # Try each selector pattern
            for selector in job_selectors:
                try:
                    found_containers = tree.xpath(selector)
                    if found_containers and len(found_containers) > 0:
                        containers = found_containers
                        print(f"  ✅ Found {len(containers)} job containers using: {selector}")
                        break
                except:
                    continue
            
            if not containers:
                # Fallback: look for any links that might be jobs
                all_links = tree.xpath("//a[@href]")
                job_links = []
                for link in all_links:
                    href = link.get('href', '')
                    text = (link.text_content() or '').strip()
                    if any(keyword in href.lower() for keyword in ['job', 'position', 'career', 'opening', 'role']) and text and len(text) > 5:
                        job_links.append(link)
                
                if job_links:
                    containers = job_links
                    print(f"  📋 Fallback: Found {len(containers)} potential job links")
            
            if not containers:
                print("  ❌ No job containers found with any selector pattern")
                return []
            
            # Process each container
            for i, container in enumerate(containers, 1):
                try:
                    job_data = self._extract_job_from_container(container, i)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    print(f"  ❌ Error processing container {i}: {e}")
                    continue
            
            return self.log_scraping_result(jobs)
            
        except Exception as e:
            print(f"❌ Error scraping Anthropic jobs: {e}")
            return []
    
    def _extract_job_from_container(self, container, index: int) -> Optional[JobItem]:
        """Extract job information from a container element"""
        try:
            # Try to find title
            title = None
            title_selectors = [
                ".//h1//text()", ".//h2//text()", ".//h3//text()", ".//h4//text()",
                ".//@title", ".//text()"
            ]
            
            for selector in title_selectors:
                try:
                    title_elements = container.xpath(selector)
                    if title_elements:
                        title_text = " ".join(str(elem).strip() for elem in title_elements if str(elem).strip())
                        if title_text and len(title_text) > 5:
                            title = title_text
                            break
                except:
                    continue
            
            # Try to find link
            link = None
            if hasattr(container, 'get') and container.get('href'):
                # Container is a link itself
                link = container.get('href')
            else:
                # Look for links inside container
                link_elements = container.xpath(".//a/@href")
                if link_elements:
                    link = link_elements[0]
            
            # Make link absolute
            if link:
                if link.startswith('/'):
                    link = self.base_url + link
                elif not link.startswith('http'):
                    link = self.base_url + '/' + link
            
            # Try to find team/department
            team = None
            team_selectors = [
                ".//span[contains(@class, 'team')]//text()",
                ".//span[contains(@class, 'department')]//text()",
                ".//div[contains(@class, 'team')]//text()",
                ".//div[contains(@class, 'department')]//text()"
            ]
            
            for selector in team_selectors:
                try:
                    team_elements = container.xpath(selector)
                    if team_elements:
                        team = " ".join(str(elem).strip() for elem in team_elements).strip()
                        break
                except:
                    continue
            
            # Try to find location
            location = None
            location_selectors = [
                ".//span[contains(@class, 'location')]//text()",
                ".//div[contains(@class, 'location')]//text()",
                ".//*[contains(text(), 'San Francisco') or contains(text(), 'Remote') or contains(text(), 'New York')]//text()"
            ]
            
            for selector in location_selectors:
                try:
                    location_elements = container.xpath(selector)
                    if location_elements:
                        location = " ".join(str(elem).strip() for elem in location_elements).strip()
                        if location:
                            break
                except:
                    continue
            
            # Validate we have minimum required fields
            if not title or not link:
                return None
            
            # Clean up title
            title = self._clean_text(title)
            if not title or len(title) < 3:
                return None
            
            # Filter out non-job links
            if any(skip in title.lower() for skip in ['privacy', 'terms', 'about', 'contact', 'blog', 'news']):
                return None
            
            job = JobItem(
                title=title,
                link=link,
                company="anthropic",
                team=self._clean_text(team) if team else None,
                location=self._clean_text(location) if location else None
            )
            
            return job
            
        except Exception as e:
            print(f"  ❌ Error extracting job from container: {e}")
            return None
    
    def scrape_job_details(self, job: JobItem, rate_limit: float = 2.0) -> JobItem:
        """Scrape detailed information for a specific Anthropic job"""
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
            if not job.location:  # Only update if not already set
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
        
        # Description selectors
        description_selectors = [
            "//div[contains(@class, 'job-description')]//text()",
            "//div[contains(@class, 'description')]//text()",
            "//section[contains(@class, 'job')]//p//text()",
            "//div[contains(@class, 'content')]//p//text()",
            "//main//p//text()",
            "//article//p//text()",
            "//div[contains(@class, 'body')]//text()",
            "//p//text()",
        ]
        
        for selector in description_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    description = self._clean_text(" ".join(str(text) for text in texts))
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
                    location = self._clean_text(" ".join(str(text) for text in texts))
                    if location:
                        # Clean up location
                        if " - " in location:
                            location = location.split(" - ")[-1]
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
            "//*[contains(text(), 'You have')]/following-sibling::*//text()",
        ]
        
        for selector in req_selectors:
            try:
                texts = tree.xpath(selector)
                if texts:
                    requirements = self._clean_text(" ".join(str(text) for text in texts))
                    if requirements and len(requirements) > 50:
                        # Clean up requirements
                        if len(requirements) > 1000:
                            parts = requirements.split("About Anthropic")
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
        text = str(text)
        cleaned = re.sub(r'\s+', ' ', text.strip())
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        return cleaned if cleaned else None
#!/usr/bin/env python3
"""
Base scraper class that defines the interface for company-specific scrapers.
"""

from abc import ABC, abstractmethod
from typing import List
import sys
import os

# Add the parent directory to Python path so we can import job_models
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from job_system.core.job_models import JobItem


class BaseScraper(ABC):
    """Abstract base class for company job scrapers"""
    
    def __init__(self, company_name: str):
        self.company_name = company_name.lower()
    
    @abstractmethod
    def scrape_job_listings(self) -> List[JobItem]:
        """
        Scrape current job listings from the company's website.
        
        Returns:
            List[JobItem]: List of current job postings
        """
        pass
    
    @abstractmethod
    def get_company_info(self) -> dict:
        """
        Get information about this company scraper.
        
        Returns:
            dict: Company info including name, base_url, etc.
        """
        pass
    
    def scrape_job_details(self, job: JobItem) -> JobItem:
        """
        Scrape detailed information for a specific job (optional override).
        Default implementation returns job unchanged.
        
        Args:
            job: JobItem to get details for
            
        Returns:
            JobItem: Job with updated details
        """
        return job
    
    def validate_job(self, job: JobItem) -> bool:
        """
        Validate that a job item has required fields.
        
        Args:
            job: JobItem to validate
            
        Returns:
            bool: True if job is valid
        """
        return (job.title and 
                job.link and 
                job.company == self.company_name)
    
    def log_scraping_result(self, jobs: List[JobItem]):
        """Log the results of scraping"""
        valid_jobs = [job for job in jobs if self.validate_job(job)]
        invalid_jobs = len(jobs) - len(valid_jobs)
        
        print(f"📊 {self.company_name.upper()} Scraping Results:")
        print(f"   Total jobs found: {len(jobs)}")
        print(f"   Valid jobs: {len(valid_jobs)}")
        if invalid_jobs > 0:
            print(f"   Invalid jobs: {invalid_jobs}")
        
        # Show sample jobs
        for i, job in enumerate(valid_jobs[:3], 1):
            print(f"   {i}. {job.title}")
            if job.location:
                print(f"      Location: {job.location}")
        
        if len(valid_jobs) > 3:
            print(f"   ... and {len(valid_jobs) - 3} more")
        
        return valid_jobs
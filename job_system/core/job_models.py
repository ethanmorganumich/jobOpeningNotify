#!/usr/bin/env python3
"""
Generic, company-agnostic job data models.
Supports jobs from any company (OpenAI, Anthropic, etc.)
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional
import json
import os

class JobItem:
    """Generic job item that can represent jobs from any company"""
    
    def __init__(self, title: str, link: str, company: str, 
                 team: Optional[str] = None, date: Optional[str] = None, 
                 description: Optional[str] = None, requirements: Optional[str] = None, 
                 location: Optional[str] = None, posting_date: Optional[str] = None,
                 match_analysis: Optional[Dict] = None, 
                 source_data: Optional[Dict] = None):
        """
        Args:
            title: Job title
            link: URL to job posting
            company: Company name (e.g., "openai", "anthropic")
            team: Team/department (optional)
            date: Date job was scraped
            description: Job description
            requirements: Job requirements
            location: Job location
            posting_date: When job was originally posted
            match_analysis: AI analysis of job fit (added later)
            source_data: Company-specific metadata
        """
        self.title = title
        self.link = link
        self.company = company.lower()  # Normalize company name
        self.team = team
        self.date = date or datetime.now(timezone.utc).isoformat()
        self.description = description
        self.requirements = requirements
        self.location = location
        self.posting_date = posting_date
        self.match_analysis = match_analysis
        self.source_data = source_data or {}

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "title": self.title,
            "link": self.link,
            "company": self.company,
            "team": self.team,
            "date": self.date,
            "description": self.description,
            "requirements": self.requirements,
            "location": self.location,
            "posting_date": self.posting_date,
            "match_analysis": self.match_analysis,
            "source_data": self.source_data
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'JobItem':
        """Create JobItem from dictionary"""
        return cls(
            title=data['title'],
            link=data['link'],
            company=data.get('company', 'unknown'),
            team=data.get('team'),
            date=data.get('date'),
            description=data.get('description'),
            requirements=data.get('requirements'),
            location=data.get('location'),
            posting_date=data.get('posting_date'),
            match_analysis=data.get('match_analysis'),
            source_data=data.get('source_data', {})
        )

    def __eq__(self, other):
        """Two jobs are equal if they have the same link"""
        return isinstance(other, JobItem) and self.link == other.link

    def __hash__(self):
        """Hash based on job link"""
        return hash(self.link)

    def __repr__(self):
        return f"JobItem(title='{self.title}', company='{self.company}', link='{self.link[:50]}...')"


class JobList:
    """Manages a list of jobs from multiple companies"""
    
    def __init__(self, items: List[JobItem]):
        self.items = items

    @classmethod
    def load_cache(cls, cache_file: str = 'jobs_cache.json') -> 'JobList':
        """Load jobs from cache file"""
        if not os.path.exists(cache_file):
            print(f"No cache file found at {cache_file}, starting fresh")
            return cls([])
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            items = []
            for item_data in data:
                # Handle legacy format (missing company field)
                if 'company' not in item_data:
                    # Try to infer company from link
                    if 'openai.com' in item_data.get('link', ''):
                        item_data['company'] = 'openai'
                    elif 'anthropic.com' in item_data.get('link', ''):
                        item_data['company'] = 'anthropic'
                    else:
                        item_data['company'] = 'unknown'
                
                items.append(JobItem.from_dict(item_data))
            
            print(f"Loaded {len(items)} jobs from cache")
            return cls(items)
            
        except Exception as e:
            print(f"Error loading cache: {e}")
            print("Starting with empty job list")
            return cls([])

    def save_cache(self, cache_file: str = 'jobs_cache.json'):
        """Save jobs to cache file"""
        try:
            data = [item.to_dict() for item in self.items]
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved {len(self.items)} jobs to {cache_file}")
        except Exception as e:
            print(f"Error saving cache: {e}")

    def add_jobs(self, new_jobs: List[JobItem]) -> tuple[List[JobItem], List[JobItem]]:
        """
        Add new jobs to the list, preserving existing match analysis.
        Returns (newly_added_jobs, updated_jobs)
        """
        existing_by_link = {job.link: job for job in self.items}
        newly_added = []
        updated = []
        
        for new_job in new_jobs:
            existing_job = existing_by_link.get(new_job.link)
            if existing_job:
                # Job exists, preserve match analysis but update other fields
                new_job.match_analysis = existing_job.match_analysis
                # Replace existing job with updated version
                self.items = [job if job.link != new_job.link else new_job for job in self.items]
                updated.append(new_job)
            else:
                # Completely new job
                self.items.append(new_job)
                newly_added.append(new_job)
        
        return newly_added, updated

    def get_jobs_by_company(self, company: str) -> List[JobItem]:
        """Get all jobs from a specific company"""
        return [job for job in self.items if job.company.lower() == company.lower()]

    def get_unanalyzed_jobs(self) -> List[JobItem]:
        """Get jobs that don't have match analysis yet"""
        return [job for job in self.items if job.match_analysis is None and job.description]

    def get_analyzed_jobs(self) -> List[JobItem]:
        """Get jobs that have match analysis"""
        return [job for job in self.items if job.match_analysis is not None]

    def remove_jobs_not_in_list(self, current_jobs: List[JobItem], company: str = None):
        """
        Remove jobs that are no longer in the current job listings.
        If company specified, only removes jobs from that company.
        """
        current_links = {job.link for job in current_jobs}
        removed_jobs = []
        
        remaining_jobs = []
        for job in self.items:
            # If company specified, only consider jobs from that company for removal
            if company and job.company.lower() != company.lower():
                remaining_jobs.append(job)  # Keep jobs from other companies
            elif job.link in current_links:
                remaining_jobs.append(job)  # Keep current jobs
            else:
                removed_jobs.append(job)    # Remove outdated jobs
        
        self.items = remaining_jobs
        return removed_jobs

    def get_stats(self) -> Dict:
        """Get statistics about the job list"""
        companies = {}
        analyzed_count = 0
        
        for job in self.items:
            companies[job.company] = companies.get(job.company, 0) + 1
            if job.match_analysis:
                analyzed_count += 1
        
        return {
            "total_jobs": len(self.items),
            "companies": companies,
            "analyzed_jobs": analyzed_count,
            "unanalyzed_jobs": len(self.items) - analyzed_count
        }

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)
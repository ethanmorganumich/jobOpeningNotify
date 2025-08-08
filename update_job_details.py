#!/usr/bin/env python3
"""
Update existing job cache with detailed information using the improved scraper.
This script will go through jobs_cache.json and populate empty description fields.
"""

import json
import time
from openai import JobDetailScraper, JobList
import argparse

def update_job_details(cache_file='jobs_cache.json', max_jobs=None, start_from=0, rate_limit=2.0):
    """
    Update jobs in the cache with detailed information.
    
    Args:
        cache_file: Path to the jobs cache JSON file
        max_jobs: Maximum number of jobs to update (None for all)
        start_from: Index to start from (useful for resuming)
        rate_limit: Delay between requests in seconds
    """
    
    print(f"Loading jobs from {cache_file}...")
    
    # Load existing jobs
    with open(cache_file, 'r') as f:
        jobs_data = json.load(f)
    
    print(f"Found {len(jobs_data)} total jobs")
    
    # Filter jobs that need updating (empty descriptions)
    jobs_to_update = []
    for i, job in enumerate(jobs_data):
        if job.get('description') is None or job.get('description') == "Details unavailable due to site protection":
            jobs_to_update.append((i, job))
    
    print(f"Found {len(jobs_to_update)} jobs needing updates")
    
    if start_from > 0:
        jobs_to_update = jobs_to_update[start_from:]
        print(f"Starting from index {start_from}, {len(jobs_to_update)} jobs remaining")
    
    if max_jobs:
        jobs_to_update = jobs_to_update[:max_jobs]
        print(f"Limiting to {len(jobs_to_update)} jobs")
    
    if not jobs_to_update:
        print("No jobs need updating!")
        return
    
    # Initialize scraper
    print(f"Initializing scraper with {rate_limit}s rate limit...")
    scraper = JobDetailScraper(rate_limit_delay=rate_limit)
    
    # Update jobs
    updated_count = 0
    failed_count = 0
    
    for i, (job_index, job) in enumerate(jobs_to_update, 1):
        print(f"\n[{i}/{len(jobs_to_update)}] Updating: {job['title']}")
        print(f"  URL: {job['link']}")
        
        try:
            # Scrape details
            details = scraper.scrape_job_details(job['link'])
            
            # Update job data
            jobs_data[job_index]['description'] = details.get('description')
            jobs_data[job_index]['requirements'] = details.get('requirements') 
            jobs_data[job_index]['location'] = details.get('location')
            jobs_data[job_index]['posting_date'] = details.get('posting_date')
            
            if details.get('description'):
                updated_count += 1
                print(f"  ✅ Updated successfully ({len(details.get('description', ''))} chars)")
            else:
                failed_count += 1
                print(f"  ❌ No description extracted")
                
        except Exception as e:
            failed_count += 1
            print(f"  ❌ Error: {e}")
        
        # Save progress periodically
        if i % 10 == 0:
            print(f"\n💾 Saving progress... ({updated_count} updated, {failed_count} failed)")
            with open(cache_file, 'w') as f:
                json.dump(jobs_data, f, indent=2)
    
    # Final save
    print(f"\n💾 Final save...")
    with open(cache_file, 'w') as f:
        json.dump(jobs_data, f, indent=2)
    
    print(f"\n🎉 Update complete!")
    print(f"  Updated: {updated_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total processed: {len(jobs_to_update)}")

def main():
    parser = argparse.ArgumentParser(description='Update job cache with detailed information')
    parser.add_argument('--cache-file', default='jobs_cache.json', help='Path to jobs cache file')
    parser.add_argument('--max-jobs', type=int, help='Maximum number of jobs to update')
    parser.add_argument('--start-from', type=int, default=0, help='Index to start from')
    parser.add_argument('--rate-limit', type=float, default=2.0, help='Rate limit in seconds between requests')
    parser.add_argument('--test', action='store_true', help='Test with just the first job')
    
    args = parser.parse_args()
    
    if args.test:
        print("🧪 TEST MODE: Updating only the first job")
        update_job_details(args.cache_file, max_jobs=1, start_from=0, rate_limit=1.0)
    else:
        update_job_details(args.cache_file, args.max_jobs, args.start_from, args.rate_limit)

if __name__ == "__main__":
    main()
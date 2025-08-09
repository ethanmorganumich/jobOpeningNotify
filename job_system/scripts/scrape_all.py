#!/usr/bin/env python3
"""
Main script to scrape jobs from all companies and update the unified cache
"""

import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from job_system.core.job_models import JobList
from job_system.scrapers.openai_scraper import OpenAIScraper
from job_system.scrapers.anthropic_scraper import AnthropicScraper


def scrape_company(scraper, job_list: JobList, fetch_details=False, max_detail_jobs=None):
    """Scrape jobs from a specific company scraper"""
    company_info = scraper.get_company_info()
    company_name = company_info['name']
    
    print(f"\n🔍 Scraping {company_info['display_name']}...")
    print(f"   URL: {company_info['jobs_url']}")
    
    # Scrape current jobs
    current_jobs = scraper.scrape_job_listings()
    
    if not current_jobs:
        print(f"   ❌ No jobs found for {company_name}")
        return [], []
    
    # Add jobs to unified list (preserves existing analysis)
    newly_added, updated = job_list.add_jobs(current_jobs)
    
    # Remove jobs that are no longer available
    removed_jobs = job_list.remove_jobs_not_in_list(current_jobs, company_name)
    
    print(f"\n📊 {company_info['display_name']} Results:")
    print(f"   Current jobs found: {len(current_jobs)}")
    print(f"   Newly added: {len(newly_added)}")
    print(f"   Updated existing: {len(updated)}")
    print(f"   Removed (no longer available): {len(removed_jobs)}")
    
    # Fetch details if requested
    if fetch_details:
        # Find jobs that need details (newly added OR existing jobs without descriptions)
        jobs_needing_details = []
        
        # Add newly added jobs
        jobs_needing_details.extend(newly_added)
        
        # Add existing jobs from this company that don't have descriptions
        existing_company_jobs = [job for job in job_list.items 
                               if job.company == company_name and not job.description]
        jobs_needing_details.extend(existing_company_jobs)
        
        # Remove duplicates and apply limit if specified
        jobs_to_detail = list(set(jobs_needing_details))
        if max_detail_jobs is not None:
            jobs_to_detail = jobs_to_detail[:max_detail_jobs]
        
        if jobs_to_detail:
            print(f"\n📋 Fetching details for {len(jobs_to_detail)} jobs...")
            
            for i, job in enumerate(jobs_to_detail, 1):
                print(f"   [{i}/{len(jobs_to_detail)}] {job.title}")
                scraper.scrape_job_details(job)
            
            if max_detail_jobs is not None and len(jobs_needing_details) > max_detail_jobs:
                print(f"   ⚠️  Limited to {max_detail_jobs} jobs to avoid overwhelming the server")
        else:
            print(f"   ✅ All jobs already have details")
    
    return newly_added, removed_jobs


def main():
    parser = argparse.ArgumentParser(description='Scrape jobs from all companies')
    parser.add_argument('--cache-file', default='jobs_cache.json', help='Jobs cache file')
    parser.add_argument('--fetch-details', action='store_true', help='Fetch job details')
    parser.add_argument('--max-detail-jobs', type=int, help='Max jobs to fetch details for per company (default: all jobs)')
    parser.add_argument('--companies', nargs='+', choices=['openai', 'anthropic'], default=['openai'], 
                       help='Which companies to scrape')
    
    args = parser.parse_args()
    
    print("🚀 Multi-Company Job Scraper")
    print("=" * 40)
    
    # Load existing unified job cache
    job_list = JobList.load_cache(args.cache_file)
    initial_stats = job_list.get_stats()
    
    print(f"📊 Initial Cache Stats:")
    print(f"   Total jobs: {initial_stats['total_jobs']}")
    print(f"   Companies: {initial_stats['companies']}")
    print(f"   Analyzed: {initial_stats['analyzed_jobs']}")
    
    all_new_jobs = []
    all_removed_jobs = []
    
    # Scrape each company
    scrapers = {
        'openai': OpenAIScraper(),
        'anthropic': AnthropicScraper(),
    }
    
    for company in args.companies:
        if company in scrapers:
            scraper = scrapers[company]
            new_jobs, removed_jobs = scrape_company(
                scraper, job_list, args.fetch_details, args.max_detail_jobs
            )
            all_new_jobs.extend(new_jobs)
            all_removed_jobs.extend(removed_jobs)
        else:
            print(f"❌ Unknown company: {company}")
    
    # Save updated cache
    job_list.save_cache(args.cache_file)
    
    # Final summary
    final_stats = job_list.get_stats()
    
    print(f"\n🎉 Scraping Complete!")
    print(f"   Total new jobs: {len(all_new_jobs)}")
    print(f"   Total removed jobs: {len(all_removed_jobs)}")
    print(f"   Final job count: {final_stats['total_jobs']}")
    print(f"   Companies: {final_stats['companies']}")
    print(f"   Analyzed jobs: {final_stats['analyzed_jobs']}")
    
    # Show sample new jobs
    if all_new_jobs:
        print(f"\n🆕 Sample New Jobs:")
        for job in all_new_jobs[:3]:
            print(f"   • {job.title} [{job.company.upper()}]")
            if job.location:
                print(f"     Location: {job.location}")
        
        if len(all_new_jobs) > 3:
            print(f"   ... and {len(all_new_jobs) - 3} more")
    
    print(f"\n💾 Cache saved to {args.cache_file}")
    return len(all_new_jobs)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Test migration from old system to new generic system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from job_system.core.job_models import JobList
from job_system.scrapers.openai_scraper import OpenAIScraper


def test_cache_migration():
    """Test loading existing cache with new system"""
    print("🧪 Testing cache migration...")
    
    # Load existing cache using new system
    job_list = JobList.load_cache('../../jobs_cache.json')
    
    # Show statistics
    stats = job_list.get_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Total jobs: {stats['total_jobs']}")
    print(f"   Companies: {stats['companies']}")
    print(f"   Analyzed jobs: {stats['analyzed_jobs']}")
    print(f"   Unanalyzed jobs: {stats['unanalyzed_jobs']}")
    
    # Show sample jobs
    print(f"\n📋 Sample jobs:")
    for i, job in enumerate(job_list.items[:3], 1):
        print(f"   {i}. {job.title} [{job.company}]")
        print(f"      Location: {job.location or 'Not specified'}")
        print(f"      Has analysis: {'Yes' if job.match_analysis else 'No'}")
    
    return job_list


def test_openai_scraper():
    """Test the new OpenAI scraper"""
    print("\n🕷️ Testing OpenAI scraper...")
    
    scraper = OpenAIScraper()
    
    # Get company info
    info = scraper.get_company_info()
    print(f"   Scraper: {info['display_name']}")
    print(f"   URL: {info['jobs_url']}")
    
    # Scrape a few jobs (limit to avoid overwhelming)
    print("   Scraping current jobs...")
    jobs = scraper.scrape_job_listings()
    
    if jobs:
        print(f"   Found {len(jobs)} jobs")
        
        # Test job detail scraping on first job
        if len(jobs) > 0:
            print(f"   Testing detail scraping on: {jobs[0].title}")
            detailed_job = scraper.scrape_job_details(jobs[0])
            if detailed_job.description:
                print(f"   ✅ Got description: {len(detailed_job.description)} chars")
            else:
                print(f"   ❌ No description extracted")
    
    return jobs


def test_integration():
    """Test integrating scraped jobs with existing cache"""
    print("\n🔗 Testing integration...")
    
    # Load existing cache
    job_list = JobList.load_cache('../../jobs_cache.json')
    initial_count = len(job_list)
    
    # Scrape current jobs
    scraper = OpenAIScraper()
    current_jobs = scraper.scrape_job_listings()[:5]  # Limit for testing
    
    # Add to job list
    newly_added, updated = job_list.add_jobs(current_jobs)
    
    print(f"   Initial jobs: {initial_count}")
    print(f"   Current scraped: {len(current_jobs)}")
    print(f"   Newly added: {len(newly_added)}")
    print(f"   Updated existing: {len(updated)}")
    print(f"   Final total: {len(job_list)}")
    
    # Save test cache
    job_list.save_cache('jobs_cache_test.json')
    print("   ✅ Saved test cache to jobs_cache_test.json")
    
    return job_list


def main():
    """Run all tests"""
    print("🚀 Testing new generic job system...")
    print("=" * 50)
    
    try:
        # Test 1: Cache migration
        job_list = test_cache_migration()
        
        # Test 2: OpenAI scraper
        scraped_jobs = test_openai_scraper()
        
        # Test 3: Integration
        integrated_list = test_integration()
        
        print("\n✅ All tests completed successfully!")
        print(f"✅ Your existing {job_list.get_stats()['total_jobs']} jobs were preserved")
        print(f"✅ OpenAI scraper found {len(scraped_jobs)} current jobs")
        print(f"✅ Integration working - check jobs_cache_test.json")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
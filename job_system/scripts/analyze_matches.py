#!/usr/bin/env python3
"""
Analyze job matches using AI for all unanalyzed jobs in the cache
"""

import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from job_system.core.job_models import JobList
from job_system.core.job_matcher import JobMatcher


def main():
    parser = argparse.ArgumentParser(description='Analyze job matches for all companies')
    parser.add_argument('--cache-file', default='jobs_cache.json', help='Jobs cache file')
    parser.add_argument('--resume', default='resume.txt', help='Resume file')
    parser.add_argument('--batch-size', type=int, default=3, help='Jobs per API batch')
    parser.add_argument('--rate-limit', type=float, default=2.0, help='Seconds between batches')
    parser.add_argument('--max-jobs', type=int, help='Max jobs to analyze')
    parser.add_argument('--company', help='Only analyze jobs from specific company')
    
    # AI Provider options
    parser.add_argument('--provider', choices=['claude', 'ollama'], default='claude', 
                       help='AI provider to use (default: claude)')
    parser.add_argument('--api-key', help='Anthropic API key (for Claude provider)')
    parser.add_argument('--ollama-url', default='http://hal:11434', 
                       help='Ollama server URL (default: http://hal:11434)')
    parser.add_argument('--ollama-model', default='gpt-oss:20b', 
                       help='Ollama model name (default: gpt-oss:20b)')
    
    args = parser.parse_args()
    
    print("🤖 Multi-Company Job Matcher")
    print("=" * 40)
    
    # Initialize matcher with chosen provider
    matcher = None
    try:
        if args.provider == 'claude':
            matcher = JobMatcher(
                provider='claude',
                anthropic_api_key=args.api_key
            )
        elif args.provider == 'ollama':
            matcher = JobMatcher(
                provider='ollama', 
                ollama_url=args.ollama_url,
                ollama_model=args.ollama_model
            )
    except (ValueError, ConnectionError, ImportError) as e:
        print(f"❌ Error initializing {args.provider} provider: {e}")
        if args.provider == 'claude':
            print("Set ANTHROPIC_API_KEY environment variable or use --api-key")
        elif args.provider == 'ollama':
            print(f"Make sure Ollama is running at {args.ollama_url}")
            print("Or specify different URL with --ollama-url")
        return
    
    if matcher is None:
        print("❌ Failed to initialize matcher")
        return
    
    # Load job cache and resume
    job_list = JobList.load_cache(args.cache_file)
    resume = matcher.load_resume(args.resume)
    
    # Get statistics
    initial_stats = job_list.get_stats()
    unanalyzed_jobs = job_list.get_unanalyzed_jobs()
    
    if args.company:
        # Filter to specific company
        unanalyzed_jobs = [job for job in unanalyzed_jobs if job.company.lower() == args.company.lower()]
        print(f"🔍 Filtering to {args.company.upper()} jobs only")
    
    print(f"📊 Current Cache Stats:")
    print(f"   Total jobs: {initial_stats['total_jobs']}")
    print(f"   Companies: {initial_stats['companies']}")
    print(f"   Already analyzed: {initial_stats['analyzed_jobs']}")
    print(f"   Unanalyzed (with descriptions): {len(unanalyzed_jobs)}")
    
    if not unanalyzed_jobs:
        print("✅ All jobs already analyzed!")
        return
    
    # Show breakdown by company
    company_breakdown = {}
    for job in unanalyzed_jobs:
        company_breakdown[job.company] = company_breakdown.get(job.company, 0) + 1
    
    print(f"\n📋 Unanalyzed Jobs by Company:")
    for company, count in company_breakdown.items():
        print(f"   {company.upper()}: {count} jobs")
    
    # Analyze jobs
    jobs_analyzed = matcher.analyze_job_list(
        job_list, resume, args.batch_size, args.rate_limit, args.max_jobs
    )
    
    if jobs_analyzed > 0:
        # Save updated cache
        job_list.save_cache(args.cache_file)
        
        # Generate and show recommendations
        print(f"\n📊 Generating recommendations...")
        recommendations = matcher.generate_recommendations(job_list)
        matcher.print_recommendations(recommendations)
        
        # Company stats
        company_stats = matcher.get_company_stats(job_list)
        print(f"\n📈 Company Analysis Stats:")
        for company, stats in company_stats.items():
            if stats['analyzed'] > 0:
                print(f"   {company.upper()}: {stats['analyzed']}/{stats['total']} analyzed, "
                      f"avg fit: {stats['avg_overall_fit']:.1f}")
        
        print(f"\n💾 Updated cache saved to {args.cache_file}")
    
    print(f"\n🎉 Analysis complete! Analyzed {jobs_analyzed} jobs.")


if __name__ == "__main__":
    main()
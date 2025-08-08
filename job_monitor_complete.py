#!/usr/bin/env python3
"""
Complete Job Monitor: Scrapes jobs, preserves match analysis, and provides recommendations.
This integrates the job scraping with the match analysis system.
"""

import argparse
from openai import main as scrape_jobs, JobList
from job_analyzer_integrated import IntegratedJobAnalyzer
import os


def complete_job_workflow(args):
    """
    Complete workflow:
    1. Scrape jobs (preserves existing match analysis)
    2. Analyze any unanalyzed jobs 
    3. Show recommendations
    """
    
    print("🔄 STEP 1: Scraping current job listings...")
    print("=" * 50)
    
    # Run job scraping (will preserve match analysis)
    new_jobs = scrape_jobs(
        fetch_details=args.fetch_details, 
        max_detail_jobs=args.max_detail_jobs
    )
    
    print(f"\n✅ Job scraping complete. Found {len(new_jobs)} new jobs.")
    
    # If we have an API key, analyze jobs
    if args.analyze and (args.api_key or os.getenv('ANTHROPIC_API_KEY')):
        print("\n🤖 STEP 2: Analyzing jobs for match...")
        print("=" * 50)
        
        try:
            analyzer = IntegratedJobAnalyzer(args.api_key)
            resume = analyzer.load_resume(args.resume)
            
            # Analyze and update cache 
            updated_job_list = analyzer.analyze_and_update_cache(
                args.cache_file, resume, args.batch_size, args.rate_limit, args.max_analyze
            )
            
            print("\n📊 STEP 3: Generating recommendations...")
            print("=" * 50)
            
            # Generate and show recommendations
            recommendations = analyzer.generate_recommendations(updated_job_list)
            analyzer.print_recommendations(recommendations)
            
        except ValueError as e:
            print(f"⚠️  Skipping analysis: {e}")
            print("Set ANTHROPIC_API_KEY to enable job matching analysis")
            
    elif args.analyze:
        print("\n⚠️  ANTHROPIC_API_KEY required for analysis. Skipping...")
    
    # Always show recommendations from existing analysis
    if not args.analyze or not (args.api_key or os.getenv('ANTHROPIC_API_KEY')):
        print("\n📊 Showing recommendations from existing analysis...")
        print("=" * 50)
        
        job_list = JobList.load_cache(use_s3=False, local_file=args.cache_file)
        analyzed_jobs = [job for job in job_list.items if job.match_analysis]
        
        if analyzed_jobs:
            try:
                dummy_analyzer = IntegratedJobAnalyzer("dummy")  # Will fail but we only need methods
            except:
                pass
            
            # Create a minimal analyzer just for recommendations
            class DummyAnalyzer:
                def generate_recommendations(self, job_list, top_n=15):
                    analyzed_jobs = [job for job in job_list.items if job.match_analysis]
                    
                    if not analyzed_jobs:
                        return {}
                    
                    # Sort by different criteria
                    by_overall = sorted(analyzed_jobs, key=lambda x: x.match_analysis['overall_fit'], reverse=True)
                    by_skills = sorted(analyzed_jobs, key=lambda x: x.match_analysis['skills_match'], reverse=True)
                    by_interest = sorted(analyzed_jobs, key=lambda x: x.match_analysis['interest_alignment'], reverse=True)
                    
                    # Create balanced score
                    for job in analyzed_jobs:
                        analysis = job.match_analysis
                        analysis['balanced_score'] = (analysis['skills_match'] + analysis['interest_alignment']) / 2
                    
                    by_balanced = sorted(analyzed_jobs, key=lambda x: x.match_analysis['balanced_score'], reverse=True)
                    
                    return {
                        'best_overall_fit': by_overall[:top_n],
                        'best_skills_match': by_skills[:top_n], 
                        'best_interest_alignment': by_interest[:top_n],
                        'best_balanced_match': by_balanced[:top_n]
                    }
                
                def print_recommendations(self, recommendations):
                    if not recommendations:
                        print("❌ No analyzed jobs found. Run with --analyze to analyze jobs.")
                        return
                        
                    print("\n" + "="*80)
                    print("🎯 JOB RECOMMENDATIONS (from existing analysis)")
                    print("="*80)
                    
                    categories = [
                        ('best_balanced_match', '🎯 BEST BALANCED MATCHES - APPLY TO THESE!'),
                        ('best_overall_fit', '⭐ BEST OVERALL FIT'), 
                        ('best_skills_match', '💪 BEST SKILLS MATCH'),
                        ('best_interest_alignment', '❤️ BEST INTEREST ALIGNMENT')
                    ]
                    
                    for category, title in categories:
                        jobs = recommendations.get(category, [])
                        if not jobs:
                            continue
                            
                        print(f"\n{title}")
                        print("-" * len(title))
                        
                        for i, job in enumerate(jobs[:5], 1):
                            analysis = job.match_analysis
                            print(f"\n{i}. {job.title}")
                            print(f"   Location: {job.location or 'Not specified'}")
                            print(f"   Scores: Overall {analysis['overall_fit']}, Skills {analysis['skills_match']}, Interest {analysis['interest_alignment']}")
                            if category == 'best_balanced_match':
                                print(f"   Balanced Score: {analysis.get('balanced_score', 0):.1f}")
                            print(f"   Summary: {analysis['one_line_summary']}")
                            print(f"   URL: {job['link']}")
            
            dummy = DummyAnalyzer()
            recommendations = dummy.generate_recommendations(job_list)
            dummy.print_recommendations(recommendations)
        else:
            print("❌ No analyzed jobs found. Run with --analyze to analyze jobs.")
    
    print(f"\n🎉 Workflow complete!")
    print(f"💡 Your jobs cache at {args.cache_file} now preserves match analysis")
    print(f"💡 Re-run anytime to get new jobs and maintain your analysis")


def main():
    parser = argparse.ArgumentParser(description='Complete job monitoring with analysis')
    
    # Job scraping options
    parser.add_argument('--cache-file', default='jobs_cache.json', help='Jobs cache file')
    parser.add_argument('--fetch-details', action='store_true', default=True, help='Fetch job details')
    parser.add_argument('--max-detail-jobs', type=int, default=10, help='Max jobs to fetch details for')
    
    # Analysis options
    parser.add_argument('--analyze', action='store_true', help='Analyze jobs for match (requires ANTHROPIC_API_KEY)')
    parser.add_argument('--resume', default='resume.txt', help='Resume file path')
    parser.add_argument('--api-key', help='Anthropic API key')
    parser.add_argument('--batch-size', type=int, default=3, help='Jobs per API batch')
    parser.add_argument('--rate-limit', type=float, default=2.0, help='Seconds between API batches')
    parser.add_argument('--max-analyze', type=int, help='Max jobs to analyze')
    
    # Quick options
    parser.add_argument('--recommendations-only', action='store_true', help='Only show recommendations')
    parser.add_argument('--scrape-only', action='store_true', help='Only scrape jobs, no analysis')
    
    args = parser.parse_args()
    
    if args.recommendations_only:
        # Just show recommendations
        print("📊 Showing recommendations from existing analysis...")
        try:
            analyzer = IntegratedJobAnalyzer(args.api_key)
            job_list = JobList.load_cache(use_s3=False, local_file=args.cache_file)
            recommendations = analyzer.generate_recommendations(job_list)
            analyzer.print_recommendations(recommendations)
        except:
            print("❌ Could not load recommendations. Run full analysis first.")
        return
    
    if args.scrape_only:
        args.analyze = False
    
    complete_job_workflow(args)


if __name__ == "__main__":
    main()
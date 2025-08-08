#!/usr/bin/env python3
"""
Show job recommendations from analyzed jobs in the cache
"""

import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from job_system.core.job_models import JobList
from job_system.core.job_matcher import JobMatcher


def main():
    parser = argparse.ArgumentParser(description='Show job recommendations from cache')
    parser.add_argument('--cache-file', default='jobs_cache.json', help='Jobs cache file')
    parser.add_argument('--top-n', type=int, default=15, help='Number of top jobs to show per category')
    parser.add_argument('--company', help='Only show jobs from specific company')
    parser.add_argument('--min-score', type=int, help='Minimum overall fit score to show')
    
    args = parser.parse_args()
    
    print("🎯 Job Recommendations")
    print("=" * 40)
    
    # Load job cache
    job_list = JobList.load_cache(args.cache_file)
    
    # Get statistics
    stats = job_list.get_stats()
    analyzed_jobs = job_list.get_analyzed_jobs()
    
    print(f"📊 Cache Statistics:")
    print(f"   Total jobs: {stats['total_jobs']}")
    print(f"   Companies: {stats['companies']}")
    print(f"   Analyzed jobs: {stats['analyzed_jobs']}")
    
    if not analyzed_jobs:
        print("\n❌ No analyzed jobs found!")
        print("Run analyze_matches.py first to analyze jobs.")
        return
    
    # Filter by company if specified
    if args.company:
        analyzed_jobs = [job for job in analyzed_jobs if job.company.lower() == args.company.lower()]
        print(f"\n🔍 Filtered to {args.company.upper()}: {len(analyzed_jobs)} jobs")
    
    # Filter by minimum score if specified
    if args.min_score:
        analyzed_jobs = [job for job in analyzed_jobs if job.match_analysis['overall_fit'] >= args.min_score]
        print(f"🎯 Filtered to min score {args.min_score}: {len(analyzed_jobs)} jobs")
    
    if not analyzed_jobs:
        print("❌ No jobs match the specified filters!")
        return
    
    # Create a minimal matcher just for recommendations
    try:
        # We just need the recommendation methods, not the API
        dummy_matcher = JobMatcher("dummy")
    except:
        # Create minimal recommendation logic
        class MinimalMatcher:
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
                    return
                    
                print("\n" + "="*80)
                print("🎯 JOB RECOMMENDATIONS")
                print("="*80)
                
                categories = [
                    ('best_balanced_match', '🎯 BEST BALANCED MATCHES (Skills + Interest) - APPLY TO THESE!'),
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
                    
                    for i, job in enumerate(jobs[:8], 1):
                        analysis = job.match_analysis
                        company_display = job.company.upper()
                        print(f"\n{i}. {job.title} [{company_display}]")
                        print(f"   Location: {job.location or 'Not specified'}")
                        if job.team:
                            print(f"   Team: {job.team}")
                        print(f"   Scores: Overall {analysis['overall_fit']}, Skills {analysis['skills_match']}, Interest {analysis['interest_alignment']}")
                        if category == 'best_balanced_match':
                            print(f"   Balanced Score: {analysis.get('balanced_score', 0):.1f}")
                        print(f"   Summary: {analysis['one_line_summary']}")
                        print(f"   Excitement: {analysis['excitement_factor']}")
                        print(f"   URL: {job.link}")
        
        dummy_matcher = MinimalMatcher()
    
    # Create a temporary job list with filtered jobs
    class FilteredJobList:
        def __init__(self, jobs):
            self.items = jobs
    
    filtered_job_list = FilteredJobList(analyzed_jobs)
    
    # Generate and show recommendations
    recommendations = dummy_matcher.generate_recommendations(filtered_job_list, args.top_n)
    dummy_matcher.print_recommendations(recommendations)
    
    # Show company breakdown
    company_breakdown = {}
    for job in analyzed_jobs:
        company = job.company
        if company not in company_breakdown:
            company_breakdown[company] = {'count': 0, 'avg_score': 0, 'scores': []}
        company_breakdown[company]['count'] += 1
        company_breakdown[company]['scores'].append(job.match_analysis['overall_fit'])
    
    print(f"\n📈 Company Breakdown:")
    for company, data in company_breakdown.items():
        avg_score = sum(data['scores']) / len(data['scores'])
        print(f"   {company.upper()}: {data['count']} jobs, avg fit: {avg_score:.1f}")
    
    print(f"\n💡 Tip: Focus on 'BEST BALANCED MATCHES' - these combine skills and interests!")


if __name__ == "__main__":
    main()
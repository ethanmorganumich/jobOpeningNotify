#!/usr/bin/env python3
"""
Integrated Job Analyzer: Adds match analysis to existing jobs cache.
Only analyzes jobs that don't already have match_analysis to save costs.
"""

import json
import argparse
from typing import List, Dict, Optional
import os
import anthropic as anthropic_client
import time
import re
from openai import JobList, JobItem

class IntegratedJobAnalyzer:
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize job analyzer with AI client"""
        if anthropic_api_key:
            self.client = anthropic_client.Anthropic(api_key=anthropic_api_key)
        elif os.getenv('ANTHROPIC_API_KEY'):
            self.client = anthropic_client.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        else:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter required")
    
    def load_resume(self, resume_file: str) -> str:
        """Load resume content"""
        with open(resume_file, 'r') as f:
            resume = f.read()
        print(f"Loaded resume ({len(resume)} characters)")
        return resume
    
    def find_unanalyzed_jobs(self, job_list: JobList) -> List[JobItem]:
        """Find jobs that don't have match analysis yet"""
        unanalyzed = []
        for job in job_list.items:
            if (job.description and  # Only analyze jobs with descriptions
                job.match_analysis is None):  # No existing analysis
                unanalyzed.append(job)
        
        print(f"Found {len(unanalyzed)} jobs needing analysis out of {len(job_list.items)} total")
        return unanalyzed
    
    def analyze_job_batch(self, jobs_batch: List[JobItem], resume: str) -> List[Dict]:
        """
        Analyze multiple jobs in a single API call for efficiency.
        """
        
        # Build batch prompt
        jobs_text = ""
        for i, job in enumerate(jobs_batch, 1):
            jobs_text += f"""

JOB {i}:
Title: {job.title}
Location: {job.location or 'Not specified'}
Description: {job.description[:1500]}{'...' if len(job.description) > 1500 else ''}
"""
        
        prompt = f"""
You are a career advisor analyzing job fit. Evaluate these {len(jobs_batch)} job postings against the candidate's resume.

CANDIDATE RESUME:
{resume}

JOBS TO ANALYZE:
{jobs_text}

For EACH job, analyze and score (0-100) on these dimensions:

1. SKILLS MATCH: How well do the candidate's technical skills and experience align with job requirements?
   Consider: programming languages, systems experience, scale of previous work, technical depth

2. EXPERIENCE MATCH: How well does their background prepare them for this role?  
   Consider: AWS experience, distributed systems, AI/ML work, leadership, similar domains

3. INTEREST ALIGNMENT: Based on stated interests (ML, distributed systems, product), how excited would they be?
   Consider: role focus areas, growth opportunities, alignment with stated interests

4. OVERALL FIT: Considering all factors, how good a match is this?

Respond with a JSON array containing one object per job in the EXACT same order:

[
  {{
    "job_number": 1,
    "skills_match": <score 0-100>,
    "experience_match": <score 0-100>,
    "interest_alignment": <score 0-100>,
    "overall_fit": <score 0-100>,
    "key_strengths": ["strength1", "strength2"],
    "potential_gaps": ["gap1", "gap2"],
    "excitement_factor": "brief reason why exciting",
    "one_line_summary": "one sentence summary of fit",
    "analysis_date": "{time.strftime('%Y-%m-%d')}"
  }},
  ... (continue for all {len(jobs_batch)} jobs)
]
"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract text from response
            response_text = response.content[0].text
            
            # Try to find JSON array in response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                analyses = json.loads(json_str)
                
                # Validate we got the right number of analyses
                if len(analyses) != len(jobs_batch):
                    print(f"  ⚠️  Expected {len(jobs_batch)} analyses, got {len(analyses)}")
                    # Pad or truncate to match
                    while len(analyses) < len(jobs_batch):
                        analyses.append(self._get_fallback_analysis())
                    analyses = analyses[:len(jobs_batch)]
                
                return analyses
            else:
                raise ValueError("No JSON array found in response")
                
        except json.JSONDecodeError as e:
            print(f"  ❌ JSON Parse Error: {e}")
            print(f"  Response text: {response_text[:300]}...")
            return [self._get_fallback_analysis() for _ in jobs_batch]
        except Exception as e:
            print(f"  ❌ API Error: {e}")
            return [self._get_fallback_analysis() for _ in jobs_batch]
    
    def _get_fallback_analysis(self) -> Dict:
        """Return fallback analysis when API call fails"""
        return {
            "skills_match": 0,
            "experience_match": 0,
            "interest_alignment": 0,
            "overall_fit": 0,
            "key_strengths": [],
            "potential_gaps": ["Analysis failed"],
            "excitement_factor": "Could not analyze",
            "one_line_summary": "Analysis failed - API error",
            "analysis_date": time.strftime('%Y-%m-%d')
        }
    
    def analyze_and_update_cache(self, cache_file: str, resume: str, 
                                batch_size: int = 3, rate_limit: float = 2.0, 
                                max_jobs: Optional[int] = None) -> JobList:
        """
        Load job cache, analyze unanalyzed jobs, and save back to cache.
        Returns the updated JobList.
        """
        
        # Load existing cache
        print(f"Loading job cache from {cache_file}...")
        job_list = JobList.load_cache(
            use_s3=False, 
            local_file=cache_file
        )
        
        # Find jobs needing analysis
        unanalyzed_jobs = self.find_unanalyzed_jobs(job_list)
        
        if max_jobs:
            unanalyzed_jobs = unanalyzed_jobs[:max_jobs]
            print(f"Limited to first {max_jobs} unanalyzed jobs")
        
        if not unanalyzed_jobs:
            print("✅ All jobs already analyzed!")
            return job_list
        
        # Calculate cost
        total_batches = (len(unanalyzed_jobs) + batch_size - 1) // batch_size
        estimated_cost = total_batches * 0.027  # Rough estimate per batch
        
        print(f"\n💰 ANALYSIS PLAN:")
        print(f"   Jobs to analyze: {len(unanalyzed_jobs)}")
        print(f"   Batches needed: {total_batches}")
        print(f"   Estimated cost: ~${estimated_cost:.3f}")
        
        confirm = input(f"\nProceed with analysis? (y/n): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return job_list
        
        # Process in batches
        print(f"\n🚀 Processing {len(unanalyzed_jobs)} jobs in {total_batches} batches...")
        
        for batch_idx in range(0, len(unanalyzed_jobs), batch_size):
            batch_jobs = unanalyzed_jobs[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(batch_jobs)} jobs:")
            for job in batch_jobs:
                print(f"  - {job.title}")
            
            # Analyze this batch
            batch_analyses = self.analyze_job_batch(batch_jobs, resume)
            
            # Update job objects with analysis
            for job, analysis in zip(batch_jobs, batch_analyses):
                job.match_analysis = analysis
                print(f"    ✅ {job.title}: Overall {analysis['overall_fit']}/100")
            
            # Save progress after each batch
            print(f"  💾 Saving progress...")
            job_list.save_cache(use_s3=False, local_file=cache_file)
            
            # Rate limiting between batches
            if batch_num < total_batches:
                print(f"  💤 Waiting {rate_limit}s before next batch...")
                time.sleep(rate_limit)
        
        print(f"\n🎉 Analysis complete! Updated {len(unanalyzed_jobs)} jobs.")
        return job_list
    
    def generate_recommendations(self, job_list: JobList, top_n: int = 15) -> Dict[str, List[JobItem]]:
        """Generate ranked recommendations from analyzed jobs"""
        
        # Filter jobs with analysis
        analyzed_jobs = [job for job in job_list.items if job.match_analysis]
        
        if not analyzed_jobs:
            print("❌ No jobs have been analyzed yet!")
            return {}
        
        print(f"📊 Generating recommendations from {len(analyzed_jobs)} analyzed jobs...")
        
        # Sort jobs by different criteria
        by_overall = sorted(analyzed_jobs, key=lambda x: x.match_analysis['overall_fit'], reverse=True)
        by_skills = sorted(analyzed_jobs, key=lambda x: x.match_analysis['skills_match'], reverse=True)
        by_interest = sorted(analyzed_jobs, key=lambda x: x.match_analysis['interest_alignment'], reverse=True)
        
        # Create balanced score (skills + interest)
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
    
    def print_recommendations(self, recommendations: Dict[str, List[JobItem]]):
        """Print formatted recommendations"""
        
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
            
            for i, job in enumerate(jobs[:8], 1):  # Show top 8
                analysis = job.match_analysis
                print(f"\n{i}. {job.title}")
                print(f"   Location: {job.location or 'Not specified'}")
                print(f"   Scores: Overall {analysis['overall_fit']}, Skills {analysis['skills_match']}, Interest {analysis['interest_alignment']}")
                if category == 'best_balanced_match':
                    print(f"   Balanced Score: {analysis.get('balanced_score', 0):.1f}")
                print(f"   Summary: {analysis['one_line_summary']}")
                print(f"   Excitement: {analysis['excitement_factor']}")
                print(f"   URL: {job.link}")


def main():
    parser = argparse.ArgumentParser(description='Integrated job analysis with persistent cache')
    parser.add_argument('--cache-file', default='jobs_cache.json', help='Path to jobs cache file')
    parser.add_argument('--resume', default='resume.txt', help='Path to resume file') 
    parser.add_argument('--batch-size', type=int, default=3, help='Jobs per API call (3-5 recommended)')
    parser.add_argument('--rate-limit', type=float, default=2.0, help='Seconds between batches')
    parser.add_argument('--max-jobs', type=int, help='Limit number of jobs to analyze')
    parser.add_argument('--api-key', help='Anthropic API key (or set ANTHROPIC_API_KEY env var)')
    parser.add_argument('--recommendations-only', action='store_true', help='Just show recommendations from existing analysis')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    try:
        analyzer = IntegratedJobAnalyzer(args.api_key)
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set ANTHROPIC_API_KEY environment variable or use --api-key")
        return
    
    if args.recommendations_only:
        # Just load cache and show recommendations
        job_list = JobList.load_cache(use_s3=False, local_file=args.cache_file)
        recommendations = analyzer.generate_recommendations(job_list)
        analyzer.print_recommendations(recommendations)
        return
    
    # Load resume
    resume = analyzer.load_resume(args.resume)
    
    # Analyze jobs and update cache
    updated_job_list = analyzer.analyze_and_update_cache(
        args.cache_file, resume, args.batch_size, args.rate_limit, args.max_jobs
    )
    
    # Generate and show recommendations
    recommendations = analyzer.generate_recommendations(updated_job_list)
    analyzer.print_recommendations(recommendations)
    
    print(f"\n💡 Your job cache now includes match analysis!")
    print(f"💡 Run with --recommendations-only to view recommendations without re-analyzing")
    print(f"💡 New jobs will be analyzed automatically when you run this again")

if __name__ == "__main__":
    main()
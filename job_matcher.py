#!/usr/bin/env python3
"""
Job Matcher: Analyze job postings against resume and interests to find best matches.

This script will:
1. Load job listings from jobs_cache.json
2. Load resume from resume.txt
3. Use AI to analyze each job for skills match and interest alignment
4. Generate ranked recommendations
"""

import json
import argparse
from typing import List, Dict, Optional
import os
import anthropic as anthropic_client
import time

class JobMatcher:
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize job matcher with AI client"""
        if anthropic_api_key:
            self.client = anthropic_client.Anthropic(api_key=anthropic_api_key)
        elif os.getenv('ANTHROPIC_API_KEY'):
            self.client = anthropic_client.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        else:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter required")
    
    def load_jobs(self, cache_file: str) -> List[Dict]:
        """Load jobs from cache file"""
        with open(cache_file, 'r') as f:
            jobs = json.load(f)
        
        # Filter jobs that have descriptions
        jobs_with_descriptions = [job for job in jobs if job.get('description')]
        print(f"Loaded {len(jobs)} total jobs, {len(jobs_with_descriptions)} with descriptions")
        return jobs_with_descriptions
    
    def load_resume(self, resume_file: str) -> str:
        """Load resume content"""
        with open(resume_file, 'r') as f:
            resume = f.read()
        print(f"Loaded resume ({len(resume)} characters)")
        return resume
    
    def analyze_job_match(self, job: Dict, resume: str) -> Dict:
        """
        Use AI to analyze how well a job matches the resume and interests.
        Returns scores and reasoning.
        """
        prompt = f"""
You are a career advisor analyzing job fit. Evaluate this job posting against the candidate's resume.

CANDIDATE RESUME:
{resume}

JOB POSTING:
Title: {job['title']}
Location: {job.get('location', 'Not specified')}
Description: {job['description'][:2000]}{'...' if len(job['description']) > 2000 else ''}

Please analyze and score (0-100) on these dimensions:

1. SKILLS MATCH: How well do the candidate's technical skills and experience align with job requirements?
   Consider: programming languages, systems experience, scale of previous work, technical depth

2. EXPERIENCE MATCH: How well does their background prepare them for this role?
   Consider: AWS experience, distributed systems, AI/ML work, leadership, similar domains

3. INTEREST ALIGNMENT: Based on stated interests (ML, distributed systems, product), how excited would they be?
   Consider: role focus areas, growth opportunities, alignment with stated interests

4. OVERALL FIT: Considering all factors, how good a match is this?

Respond in this exact JSON format:
{{
  "skills_match": <score 0-100>,
  "experience_match": <score 0-100>, 
  "interest_alignment": <score 0-100>,
  "overall_fit": <score 0-100>,
  "key_strengths": ["strength1", "strength2", "strength3"],
  "potential_gaps": ["gap1", "gap2"],
  "excitement_factor": "<why this would be exciting>",
  "one_line_summary": "<one sentence summary of fit>"
}}
"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract text from response
            response_text = response.content[0].text
            
            # Try to find JSON in response (in case there's extra text)
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                analysis = json.loads(json_str)
                return analysis
            else:
                # Fallback if no JSON found
                raise ValueError("No JSON found in response")
                
        except json.JSONDecodeError as e:
            print(f"  JSON Parse Error: {e}")
            print(f"  Response text: {response_text[:200]}...")
            return self._get_fallback_analysis()
        except Exception as e:
            print(f"  API Error: {e}")
            return self._get_fallback_analysis()
    
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
            "one_line_summary": "Analysis failed - API error"
        }
    
    def analyze_all_jobs(self, jobs: List[Dict], resume: str, rate_limit: float = 1.0) -> List[Dict]:
        """Analyze all jobs and return with match scores"""
        results = []
        
        for i, job in enumerate(jobs, 1):
            print(f"\n[{i}/{len(jobs)}] Analyzing: {job['title']}")
            
            analysis = self.analyze_job_match(job, resume)
            
            # Combine job data with analysis
            job_result = job.copy()
            job_result['match_analysis'] = analysis
            results.append(job_result)
            
            print(f"  Overall Fit: {analysis['overall_fit']}/100")
            print(f"  Skills: {analysis['skills_match']}, Experience: {analysis['experience_match']}, Interest: {analysis['interest_alignment']}")
            
            # Rate limiting
            if i < len(jobs):  # Don't sleep after last job
                time.sleep(rate_limit)
        
        return results
    
    def generate_recommendations(self, analyzed_jobs: List[Dict]) -> Dict[str, List[Dict]]:
        """Generate different recommendation lists"""
        
        # Sort jobs by different criteria
        by_overall = sorted(analyzed_jobs, key=lambda x: x['match_analysis']['overall_fit'], reverse=True)
        by_skills = sorted(analyzed_jobs, key=lambda x: x['match_analysis']['skills_match'], reverse=True)
        by_interest = sorted(analyzed_jobs, key=lambda x: x['match_analysis']['interest_alignment'], reverse=True)
        
        # Create balanced score (skills + interest)
        for job in analyzed_jobs:
            analysis = job['match_analysis']
            analysis['balanced_score'] = (analysis['skills_match'] + analysis['interest_alignment']) / 2
        
        by_balanced = sorted(analyzed_jobs, key=lambda x: x['match_analysis']['balanced_score'], reverse=True)
        
        return {
            'best_overall_fit': by_overall[:10],
            'best_skills_match': by_skills[:10], 
            'best_interest_alignment': by_interest[:10],
            'best_balanced_match': by_balanced[:10]
        }
    
    def save_results(self, results: List[Dict], recommendations: Dict, output_file: str):
        """Save analysis results to JSON file"""
        output = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_jobs_analyzed': len(results),
            'recommendations': recommendations,
            'all_results': results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Results saved to {output_file}")
    
    def print_recommendations(self, recommendations: Dict):
        """Print formatted recommendations"""
        
        print("\n" + "="*80)
        print("🎯 JOB RECOMMENDATIONS")
        print("="*80)
        
        categories = [
            ('best_balanced_match', '🎯 BEST BALANCED MATCHES (Skills + Interest)'),
            ('best_overall_fit', '⭐ BEST OVERALL FIT'), 
            ('best_skills_match', '💪 BEST SKILLS MATCH'),
            ('best_interest_alignment', '❤️ BEST INTEREST ALIGNMENT')
        ]
        
        for category, title in categories:
            jobs = recommendations[category]
            print(f"\n{title}")
            print("-" * len(title))
            
            for i, job in enumerate(jobs[:5], 1):  # Show top 5
                analysis = job['match_analysis']
                print(f"\n{i}. {job['title']}")
                print(f"   Location: {job.get('location', 'Not specified')}")
                print(f"   Scores: Overall {analysis['overall_fit']}, Skills {analysis['skills_match']}, Interest {analysis['interest_alignment']}")
                print(f"   Summary: {analysis['one_line_summary']}")
                print(f"   URL: {job['link']}")

def main():
    parser = argparse.ArgumentParser(description='Match jobs against resume and interests')
    parser.add_argument('--jobs-cache', default='jobs_cache.json', help='Path to jobs cache file')
    parser.add_argument('--resume', default='resume.txt', help='Path to resume file') 
    parser.add_argument('--output', default='job_matches.json', help='Output file for results')
    parser.add_argument('--rate-limit', type=float, default=1.0, help='Seconds between API calls')
    parser.add_argument('--max-jobs', type=int, help='Limit number of jobs to analyze')
    parser.add_argument('--api-key', help='Anthropic API key (or set ANTHROPIC_API_KEY env var)')
    
    args = parser.parse_args()
    
    # Initialize matcher
    try:
        matcher = JobMatcher(args.api_key)
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set ANTHROPIC_API_KEY environment variable or use --api-key")
        return
    
    # Load data
    jobs = matcher.load_jobs(args.jobs_cache)
    resume = matcher.load_resume(args.resume)
    
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
        print(f"Limited to first {len(jobs)} jobs for analysis")
    
    # Analyze jobs
    print(f"\n🤖 Starting analysis of {len(jobs)} jobs...")
    analyzed_jobs = matcher.analyze_all_jobs(jobs, resume, args.rate_limit)
    
    # Generate recommendations
    print(f"\n📊 Generating recommendations...")
    recommendations = matcher.generate_recommendations(analyzed_jobs)
    
    # Save and display results
    matcher.save_results(analyzed_jobs, recommendations, args.output)
    matcher.print_recommendations(recommendations)
    
    print(f"\n🎉 Analysis complete! Check {args.output} for detailed results.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Optimized Job Matcher: Batch process multiple jobs per API call for better efficiency and lower cost.
"""

import json
import argparse
from typing import List, Dict, Optional
import os
import anthropic as anthropic_client
import time
import re

class BatchJobMatcher:
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
    
    def analyze_job_batch(self, jobs_batch: List[Dict], resume: str) -> List[Dict]:
        """
        Analyze multiple jobs in a single API call for efficiency.
        This reduces API calls by ~5-10x and cost significantly.
        """
        
        # Build batch prompt
        jobs_text = ""
        for i, job in enumerate(jobs_batch, 1):
            jobs_text += f"""

JOB {i}:
Title: {job['title']}
Location: {job.get('location', 'Not specified')}
Description: {job['description'][:1500]}{'...' if len(job['description']) > 1500 else ''}
Link: {job['link']}
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
    "one_line_summary": "one sentence summary of fit"
  }},
  ... (continue for all {len(jobs_batch)} jobs)
]
"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Using Sonnet for better batch processing
                max_tokens=4000,  # More tokens for batch processing
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
            "one_line_summary": "Analysis failed - API error"
        }
    
    def analyze_all_jobs(self, jobs: List[Dict], resume: str, batch_size: int = 3, rate_limit: float = 2.0) -> List[Dict]:
        """Analyze all jobs in batches for efficiency"""
        results = []
        total_batches = (len(jobs) + batch_size - 1) // batch_size
        
        print(f"\n🚀 Processing {len(jobs)} jobs in {total_batches} batches of {batch_size}")
        
        for batch_idx in range(0, len(jobs), batch_size):
            batch_jobs = jobs[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(batch_jobs)} jobs:")
            for job in batch_jobs:
                print(f"  - {job['title']}")
            
            # Analyze this batch
            batch_analyses = self.analyze_job_batch(batch_jobs, resume)
            
            # Combine results
            for job, analysis in zip(batch_jobs, batch_analyses):
                job_result = job.copy()
                job_result['match_analysis'] = analysis
                results.append(job_result)
                
                print(f"    ✅ {job['title']}: Overall {analysis['overall_fit']}/100")
            
            # Rate limiting between batches
            if batch_num < total_batches:
                print(f"  💤 Waiting {rate_limit}s before next batch...")
                time.sleep(rate_limit)
        
        return results
    
    def calculate_cost_estimate(self, num_jobs: int, batch_size: int = 3) -> Dict[str, float]:
        """Calculate estimated cost for analyzing jobs"""
        total_batches = (num_jobs + batch_size - 1) // batch_size
        
        # Rough estimates for Claude-3.5-Sonnet pricing
        input_tokens_per_batch = 2000 + (batch_size * 1000)  # Resume + job descriptions
        output_tokens_per_batch = 800  # JSON response
        
        total_input_tokens = total_batches * input_tokens_per_batch
        total_output_tokens = total_batches * output_tokens_per_batch
        
        # Claude-3.5-Sonnet pricing (approximate)
        input_cost_per_token = 0.000003  # $3 per 1M tokens
        output_cost_per_token = 0.000015  # $15 per 1M tokens
        
        input_cost = total_input_tokens * input_cost_per_token
        output_cost = total_output_tokens * output_cost_per_token
        total_cost = input_cost + output_cost
        
        return {
            "total_batches": total_batches,
            "estimated_input_tokens": total_input_tokens,
            "estimated_output_tokens": total_output_tokens,
            "estimated_input_cost": input_cost,
            "estimated_output_cost": output_cost,
            "estimated_total_cost": total_cost
        }
    
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
            'best_overall_fit': by_overall[:15],
            'best_skills_match': by_skills[:15], 
            'best_interest_alignment': by_interest[:15],
            'best_balanced_match': by_balanced[:15]
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
            ('best_balanced_match', '🎯 BEST BALANCED MATCHES (Skills + Interest) - APPLY TO THESE!'),
            ('best_overall_fit', '⭐ BEST OVERALL FIT'), 
            ('best_skills_match', '💪 BEST SKILLS MATCH'),
            ('best_interest_alignment', '❤️ BEST INTEREST ALIGNMENT')
        ]
        
        for category, title in categories:
            jobs = recommendations[category]
            print(f"\n{title}")
            print("-" * len(title))
            
            for i, job in enumerate(jobs[:8], 1):  # Show top 8
                analysis = job['match_analysis']
                print(f"\n{i}. {job['title']}")
                print(f"   Location: {job.get('location', 'Not specified')}")
                print(f"   Scores: Overall {analysis['overall_fit']}, Skills {analysis['skills_match']}, Interest {analysis['interest_alignment']}")
                if category == 'best_balanced_match':
                    print(f"   Balanced Score: {analysis.get('balanced_score', 0):.1f}")
                print(f"   Summary: {analysis['one_line_summary']}")
                print(f"   Excitement: {analysis['excitement_factor']}")
                print(f"   URL: {job['link']}")

def main():
    parser = argparse.ArgumentParser(description='Batch match jobs against resume (optimized)')
    parser.add_argument('--jobs-cache', default='jobs_cache.json', help='Path to jobs cache file')
    parser.add_argument('--resume', default='resume.txt', help='Path to resume file') 
    parser.add_argument('--output', default='job_matches_batch.json', help='Output file for results')
    parser.add_argument('--batch-size', type=int, default=3, help='Jobs per API call (3-5 recommended)')
    parser.add_argument('--rate-limit', type=float, default=2.0, help='Seconds between batches')
    parser.add_argument('--max-jobs', type=int, help='Limit number of jobs to analyze')
    parser.add_argument('--api-key', help='Anthropic API key (or set ANTHROPIC_API_KEY env var)')
    parser.add_argument('--cost-only', action='store_true', help='Just show cost estimate')
    
    args = parser.parse_args()
    
    # Initialize matcher
    try:
        matcher = BatchJobMatcher(args.api_key)
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set ANTHROPIC_API_KEY environment variable or use --api-key")
        return
    
    # Load data
    jobs = matcher.load_jobs(args.jobs_cache)
    
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
        print(f"Limited to first {len(jobs)} jobs for analysis")
    
    # Cost estimation
    cost_info = matcher.calculate_cost_estimate(len(jobs), args.batch_size)
    print(f"\n💰 COST ESTIMATE:")
    print(f"   Jobs to analyze: {len(jobs)}")
    print(f"   Batches needed: {cost_info['total_batches']}")
    print(f"   Estimated cost: ${cost_info['estimated_total_cost']:.3f}")
    print(f"   (Input: ${cost_info['estimated_input_cost']:.3f}, Output: ${cost_info['estimated_output_cost']:.3f})")
    
    if args.cost_only:
        return
    
    print(f"\n⚠️  This will cost approximately ${cost_info['estimated_total_cost']:.3f}")
    confirm = input("Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    resume = matcher.load_resume(args.resume)
    
    # Analyze jobs
    print(f"\n🤖 Starting batch analysis of {len(jobs)} jobs...")
    analyzed_jobs = matcher.analyze_all_jobs(jobs, resume, args.batch_size, args.rate_limit)
    
    # Generate recommendations
    print(f"\n📊 Generating recommendations...")
    recommendations = matcher.generate_recommendations(analyzed_jobs)
    
    # Save and display results
    matcher.save_results(analyzed_jobs, recommendations, args.output)
    matcher.print_recommendations(recommendations)
    
    print(f"\n🎉 Analysis complete! Check {args.output} for detailed results.")
    print(f"💡 Focus on the 'BEST BALANCED MATCHES' - those are your top targets!")

if __name__ == "__main__":
    main()
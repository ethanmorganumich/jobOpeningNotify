#!/usr/bin/env python3
"""
Generic job matcher - works with jobs from any company
"""

import json
import time
from typing import List, Dict, Optional
import os
import anthropic as anthropic_client
import re
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from job_system.core.job_models import JobItem, JobList


class JobMatcher:
    """Analyzes job fit using AI, works with any company's jobs"""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize job matcher with AI client"""
        if anthropic_api_key:
            self.client = anthropic_client.Anthropic(api_key=anthropic_api_key)
        elif os.getenv('ANTHROPIC_API_KEY'):
            self.client = anthropic_client.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        else:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter required")
    
    def load_resume(self, resume_file: str = 'resume.txt') -> str:
        """Load resume content"""
        with open(resume_file, 'r') as f:
            resume = f.read()
        print(f"📄 Loaded resume ({len(resume)} characters)")
        return resume
    
    def analyze_job_batch(self, jobs_batch: List[JobItem], resume: str) -> List[Dict]:
        """Analyze multiple jobs in a single API call for efficiency"""
        
        # Build batch prompt
        jobs_text = ""
        for i, job in enumerate(jobs_batch, 1):
            company_display = job.company.upper()
            jobs_text += f"""

JOB {i} ({company_display}):
Title: {job.title}
Company: {company_display}
Location: {job.location or 'Not specified'}
Team: {job.team or 'Not specified'}
Description: {(job.description or '')[:1500]}{'...' if len(job.description or '') > 1500 else ''}
"""
        
        prompt = f"""
You are a strict technical recruiter analyzing job fit. Be CRITICAL and use the FULL scoring range 0-100.

CANDIDATE RESUME:
{resume}

JOBS TO ANALYZE:
{jobs_text}

CRITICAL EVALUATION CRITERIA:

1. EXPERIENCE LEVEL MATCH (0-100):
   - Look for EXPLICIT years of experience required (e.g., "5+ years", "senior", "staff")
   - If job requires significantly more experience than candidate has, score LOW (0-30)
   - If job is entry/junior level and candidate is overqualified, score MEDIUM (40-70)
   - Perfect experience match gets HIGH scores (80-100)

2. ROLE TYPE COMPATIBILITY (0-100):
   - If job is MANAGEMENT role but candidate is INDIVIDUAL CONTRIBUTOR: score 0-20
   - If job requires skills candidate completely lacks: score 0-40
   - If job is completely different field (e.g., sales, marketing): score 0-30
   - Well-aligned IC roles: 60-100 based on other factors

3. TECHNICAL SKILLS MATCH (0-100):
   - Count specific technical skills mentioned in job that candidate possesses
   - Consider depth of experience in those technologies
   - Missing core required skills should significantly lower score (20-50 points)
   - Having all required skills + more gives 80-100

4. INTEREST ALIGNMENT (0-100):
   - How well does this role match stated career interests and trajectory?
   - Consider growth opportunities and learning potential

SCORING REQUIREMENTS:
- Use FULL range: Many jobs should score 20-60, only exceptional matches get 80+
- Be especially strict on experience requirements and role type
- Overall fit should reflect REALISTIC hiring probability
- A 90+ score means "perfect match, would definitely get interview"
- A 50 score means "possible fit with some gaps"
- A 20 score means "significant mismatch"

Respond with JSON array in EXACT order:

[
  {{
    "job_number": 1,
    "experience_level_match": <0-100>,
    "role_compatibility": <0-100>, 
    "skills_match": <0-100>,
    "interest_alignment": <0-100>,
    "overall_fit": <0-100>,
    "experience_gap": "specific experience gap if any",
    "key_strengths": ["strength1", "strength2"],
    "major_concerns": ["concern1", "concern2"],
    "excitement_factor": "brief reason why exciting or concerning",
    "one_line_summary": "honest assessment of realistic fit",
    "would_interview": true/false,
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
            "experience_level_match": 0,
            "role_compatibility": 0,
            "skills_match": 0,
            "interest_alignment": 0,
            "overall_fit": 0,
            "experience_gap": "Analysis failed",
            "key_strengths": [],
            "major_concerns": ["Analysis failed"],
            "excitement_factor": "Could not analyze",
            "one_line_summary": "Analysis failed - API error",
            "would_interview": False,
            "analysis_date": time.strftime('%Y-%m-%d')
        }
    
    def analyze_job_list(self, job_list: JobList, resume: str, 
                        batch_size: int = 3, rate_limit: float = 2.0, 
                        max_jobs: Optional[int] = None) -> int:
        """
        Analyze unanalyzed jobs in the job list.
        Returns number of jobs analyzed.
        """
        
        # Find unanalyzed jobs
        unanalyzed_jobs = job_list.get_unanalyzed_jobs()
        
        if max_jobs:
            unanalyzed_jobs = unanalyzed_jobs[:max_jobs]
        
        if not unanalyzed_jobs:
            print("✅ All jobs already analyzed!")
            return 0
        
        # Calculate cost estimate
        total_batches = (len(unanalyzed_jobs) + batch_size - 1) // batch_size
        estimated_cost = total_batches * 0.027  # Rough estimate per batch
        
        print(f"\n💰 ANALYSIS PLAN:")
        print(f"   Jobs to analyze: {len(unanalyzed_jobs)}")
        print(f"   Companies: {set(job.company for job in unanalyzed_jobs)}")
        print(f"   Batches needed: {total_batches}")
        print(f"   Estimated cost: ~${estimated_cost:.3f}")
        
        confirm = input(f"\nProceed with analysis? (y/n): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return 0
        
        # Process in batches
        print(f"\n🚀 Processing {len(unanalyzed_jobs)} jobs in {total_batches} batches...")
        
        jobs_analyzed = 0
        for batch_idx in range(0, len(unanalyzed_jobs), batch_size):
            batch_jobs = unanalyzed_jobs[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(batch_jobs)} jobs:")
            for job in batch_jobs:
                print(f"  - {job.title} ({job.company.upper()})")
            
            # Analyze this batch
            batch_analyses = self.analyze_job_batch(batch_jobs, resume)
            
            # Update job objects with analysis
            for job, analysis in zip(batch_jobs, batch_analyses):
                job.match_analysis = analysis
                jobs_analyzed += 1
                print(f"    ✅ {job.title}: Overall {analysis['overall_fit']}/100")
            
            # Rate limiting between batches
            if batch_num < total_batches:
                print(f"  💤 Waiting {rate_limit}s before next batch...")
                time.sleep(rate_limit)
        
        print(f"\n🎉 Analysis complete! Analyzed {jobs_analyzed} jobs.")
        return jobs_analyzed
    
    def _filter_realistic_jobs(self, jobs: List[JobItem], min_overall_fit: int = 30, 
                              min_role_compatibility: int = 40) -> List[JobItem]:
        """Filter out jobs with very low compatibility scores"""
        filtered = []
        for job in jobs:
            analysis = job.match_analysis
            
            # Check overall fit
            if analysis['overall_fit'] < min_overall_fit:
                continue
                
            # Check role compatibility if available (new format)
            if 'role_compatibility' in analysis and analysis['role_compatibility'] < min_role_compatibility:
                continue
                
            # Filter out obvious manager roles for IC candidates
            title_lower = job.title.lower()
            if any(word in title_lower for word in ['manager', 'director', 'vp', 'head of', 'chief']):
                if 'role_compatibility' in analysis and analysis['role_compatibility'] < 60:
                    continue
            
            filtered.append(job)
            
        return filtered

    def generate_recommendations(self, job_list: JobList, top_n: int = 15) -> Dict[str, List[JobItem]]:
        """Generate ranked recommendations from analyzed jobs with filtering"""
        
        analyzed_jobs = job_list.get_analyzed_jobs()
        
        if not analyzed_jobs:
            print("❌ No jobs have been analyzed yet!")
            return {}
        
        # Filter out obviously unsuitable jobs
        filtered_jobs = self._filter_realistic_jobs(analyzed_jobs)
        
        print(f"📊 Generating recommendations from {len(analyzed_jobs)} analyzed jobs ({len(filtered_jobs)} after filtering)...")
        
        if not filtered_jobs:
            print("❌ No suitable jobs found after filtering! All jobs had very low compatibility scores.")
            return {}
        
        # Sort jobs by different criteria
        by_overall = sorted(filtered_jobs, key=lambda x: x.match_analysis['overall_fit'], reverse=True)
        by_skills = sorted(filtered_jobs, key=lambda x: x.match_analysis['skills_match'], reverse=True)
        by_interest = sorted(filtered_jobs, key=lambda x: x.match_analysis['interest_alignment'], reverse=True)
        
        # Create balanced score - use new fields if available, fallback to old
        for job in filtered_jobs:
            analysis = job.match_analysis
            if 'role_compatibility' in analysis:
                # New format: weight role compatibility heavily
                analysis['balanced_score'] = (
                    analysis['skills_match'] * 0.3 + 
                    analysis['experience_level_match'] * 0.3 +
                    analysis['role_compatibility'] * 0.4
                )
            else:
                # Old format: fallback
                analysis['balanced_score'] = (analysis['skills_match'] + analysis['interest_alignment']) / 2
        
        by_balanced = sorted(filtered_jobs, key=lambda x: x.match_analysis['balanced_score'], reverse=True)
        
        return {
            'best_overall_fit': by_overall[:top_n],
            'best_skills_match': by_skills[:top_n], 
            'best_interest_alignment': by_interest[:top_n],
            'best_balanced_match': by_balanced[:top_n]
        }
    
    def print_recommendations(self, recommendations: Dict[str, List[JobItem]]):
        """Print formatted recommendations with company info"""
        
        if not recommendations:
            print("❌ No recommendations available. Analyze some jobs first!")
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
                company_display = job.company.upper()
                print(f"\n{i}. {job.title} [{company_display}]")
                print(f"   Location: {job.location or 'Not specified'}")
                print(f"   Team: {job.team or 'Not specified'}")
                # Handle both old and new analysis formats
                if 'experience_level_match' in analysis:
                    print(f"   Scores: Overall {analysis['overall_fit']}, Experience {analysis['experience_level_match']}, Role Fit {analysis['role_compatibility']}, Skills {analysis['skills_match']}")
                    print(f"   Would Interview: {'✅' if analysis.get('would_interview', False) else '❌'}")
                    if analysis.get('experience_gap'):
                        print(f"   Experience Gap: {analysis['experience_gap']}")
                else:
                    # Backwards compatibility with old format
                    print(f"   Scores: Overall {analysis['overall_fit']}, Skills {analysis['skills_match']}, Interest {analysis['interest_alignment']}")
                if category == 'best_balanced_match':
                    print(f"   Balanced Score: {analysis.get('balanced_score', 0):.1f}")
                print(f"   Summary: {analysis['one_line_summary']}")
                print(f"   Excitement: {analysis['excitement_factor']}")
                print(f"   URL: {job.link}")
    
    def get_company_stats(self, job_list: JobList) -> Dict:
        """Get statistics by company"""
        stats = {}
        for job in job_list.items:
            company = job.company
            if company not in stats:
                stats[company] = {
                    'total': 0,
                    'analyzed': 0,
                    'avg_overall_fit': 0
                }
            
            stats[company]['total'] += 1
            if job.match_analysis:
                stats[company]['analyzed'] += 1
                # Calculate running average
                current_avg = stats[company]['avg_overall_fit']
                current_count = stats[company]['analyzed']
                new_score = job.match_analysis['overall_fit']
                stats[company]['avg_overall_fit'] = ((current_avg * (current_count - 1)) + new_score) / current_count
        
        return stats
# Smart Job Monitoring System - Task Breakdown

## Project Goal
Create an intelligent job monitoring system that:
1. Scrapes job postings from target company websites
2. Compares against cached versions to detect new jobs
3. Fetches detailed job descriptions for new positions
4. Evaluates job fit against user's resume/interests
5. Sends smart notifications with relevance assessment

## Current Status
✅ Basic job listing scraper implemented (`openai.py`)  
✅ S3 cache storage functionality  
✅ Job comparison/diff detection  
✅ Local execution with `if __name__ == "__main__"`  

## Phase 1: POC - Local Job Monitoring (OpenAI only)

### Task 1.1: Fix Current Local Execution
**Objective**: Ensure the existing openai.py works reliably for local testing
- **Verification**: Run `python openai.py` successfully
- **Tasks**:
  - [ ] Update S3 configuration to use local file fallback when S3 unavailable
  - [ ] Test scraping with current OpenAI URL and XPath selectors
  - [ ] Verify job detection and console output work correctly
  - [ ] Fix any XPath issues if OpenAI website structure changed

### Task 1.2: Enhance Job Data Structure
**Objective**: Prepare JobItem class for additional data fields
- **Verification**: JobItem can store and serialize expanded job data
- **Tasks**:
  - [ ] Add fields to JobItem: `description`, `requirements`, `location`, `posting_date`
  - [ ] Update `to_dict()` and `from_dict()` methods
  - [ ] Maintain backward compatibility with existing cache files
  - [ ] Add validation for required vs optional fields

### Task 1.3: Improve Cache Management
**Objective**: Robust local caching with better error handling
- **Verification**: Cache operations work reliably offline
- **Tasks**:
  - [ ] Implement local file cache as primary option
  - [ ] Add cache validation (detect corrupted cache files)
  - [ ] Add cache migration for schema changes
  - [ ] Implement cache cleanup (remove old entries)

## Phase 2: Job Description Fetching

### Task 2.1: Job Detail Scraper
**Objective**: Extract full job descriptions from individual job pages
- **Verification**: Successfully fetch and parse job detail pages
- **Tasks**:
  - [ ] Analyze OpenAI job page structure for job details
  - [ ] Create `JobDetailScraper` class
  - [ ] Implement XPath selectors for:
    - Job description text
    - Requirements/qualifications
    - Preferred qualifications
    - Team/department info
    - Location details
    - Salary range (if available)
  - [ ] Add error handling for missing/changed page structure
  - [ ] Implement rate limiting to avoid being blocked

### Task 2.2: Enhanced Job Processing Pipeline
**Objective**: Integrate detail fetching into main workflow
- **Verification**: New jobs automatically get full details fetched
- **Tasks**:
  - [ ] Modify main() function to fetch details for new jobs
  - [ ] Add progress indicators for batch job processing
  - [ ] Implement retry logic for failed detail fetches
  - [ ] Add option to backfill details for existing cached jobs
  - [ ] Store detailed job data in enhanced cache format

### Task 2.3: Data Quality and Validation
**Objective**: Ensure scraped job data is clean and usable
- **Verification**: Scraped data is consistently formatted and complete
- **Tasks**:
  - [ ] Implement text cleaning functions (remove HTML, normalize whitespace)
  - [ ] Add data validation for required fields
  - [ ] Create fallback strategies for missing data
  - [ ] Add logging for data quality issues
  - [ ] Implement data normalization (standardize location names, etc.)

## Phase 3: Intelligence Layer (Future)

### Task 3.1: Resume/Profile Matching
- [ ] Create user profile schema (skills, interests, experience level)
- [ ] Implement keyword extraction from job descriptions
- [ ] Build matching algorithm for job-profile fit scoring
- [ ] Add machine learning or LLM integration for semantic matching

### Task 3.2: Smart Notifications
- [ ] Design notification template with relevance scores
- [ ] Implement filtering based on match quality
- [ ] Add email formatting with job details and match reasoning
- [ ] Create notification preferences system

## Implementation Guidelines

### Code Quality
- Follow existing code patterns in `openai.py`
- Add comprehensive error handling
- Include logging for debugging
- Write testable, modular functions
- Add docstrings for new functions/classes

### Testing Strategy
- Test with multiple job listings
- Verify XPath selectors don't break with website updates
- Test cache operations (save/load/diff)
- Validate data integrity after processing

### Configuration Management
- Keep scraping selectors in easily configurable constants
- Make rate limiting configurable
- Allow easy switching between local and S3 storage
- Support multiple target websites through configuration

## Success Criteria

### Phase 1 POC:
- [ ] Runs locally without errors
- [ ] Detects new OpenAI job postings
- [ ] Maintains cache correctly
- [ ] Provides clear console output

### Phase 2 Enhanced:
- [ ] Fetches complete job descriptions
- [ ] Stores enriched job data
- [ ] Handles errors gracefully
- [ ] Processes jobs efficiently

### Overall System:
- [ ] Runs autonomously (scheduled execution)
- [ ] Scales to multiple company websites
- [ ] Provides actionable job notifications
- [ ] Maintains data quality over time
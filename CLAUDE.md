# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a job monitoring system that scrapes job postings from various websites (primarily OpenAI careers page), compares them against a cached version, and can send email notifications for new job postings. The project is designed to run as an AWS Lambda function.

## Architecture

### Core Components

1. **Job Scraping System** (`openai.py`):
   - Uses `requests` + `lxml` for web scraping with XPath selectors
   - `JobItem` class represents individual job postings with title, link, team, and date
   - `JobList` class manages collections of jobs with diff functionality
   - Supports both local file and S3 caching

2. **AWS Integration**:
   - Uses `boto3` for S3 storage and SES email sending
   - Lambda deployment via SAM (Serverless Application Model)
   - Template defined in `template.yaml`

3. **Web Scraping with NovaAct** (`main.py`):
   - Uses `nova_act` library for dynamic web scraping
   - Currently configured for x.ai careers page

### Data Flow

1. Load existing job cache from S3
2. Scrape current job listings using configurable XPath selectors
3. Compare new listings against cache to find new/removed jobs
4. Send email notifications for new jobs (via AWS SES)
5. Update cache with current listings

## Development Commands

### Python Environment
- Activate virtual environment: `source jobNotify/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Run syntax check: `python -m py_compile *.py`

### Lambda Deployment
Use the provided shell script: `./package_openai.sh`

This script:
1. Activates the virtual environment
2. Generates fresh requirements.txt
3. Installs dependencies in lambda_deploy/
4. Copies openai.py as lambda_handler.py
5. Creates lambda_package.zip for deployment

### AWS SAM
- Template: `template.yaml` 
- Handler: `openai.lambda_handler`
- Runtime: Python 3.9 (configured in template)

## Configuration

### Environment Variables / Constants to Update
- `S3_BUCKET`: S3 bucket name for job cache storage
- `S3_KEY`: Key for cache file (default: 'jobs_cache.json')
- `AWS_REGION`: AWS region (default: 'us-east-1')
- `EMAIL_SENDER`: SES verified sender email
- `EMAIL_RECIPIENT`: Email recipient for notifications

### Scraping Configuration
- `URL`: Target job search URL
- `LIST_XPATH`: XPath to job listing containers
- `FIELD_BUILDERS`: Dictionary mapping field names to XPath builder functions

## Key Files

- `openai.py`: Main application logic and Lambda handler
- `main.py`: Alternative implementation using NovaAct
- `lambda_deploy/lambda_handler.py`: Deployment copy of openai.py
- `package_openai.sh`: Lambda packaging script
- `template.yaml`: AWS SAM template
- `jobs_cache.json`: Local job cache file
- `requirements.txt`: Python dependencies

## Dependencies

The project uses these key libraries:
- `boto3`: AWS SDK
- `requests`: HTTP requests
- `lxml`: HTML/XML parsing
- `nova_act`: Dynamic web scraping (for main.py)

## Testing

Run basic syntax validation with:
```bash
python -m py_compile *.py
```

No formal test suite is currently implemented.
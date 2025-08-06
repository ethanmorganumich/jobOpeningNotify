#!/usr/bin/env python3
"""
dynamic_scraper.py

Fetch a URL, scrape job postings into objects with dates,
serialize to JSON, and compute diffs against local cache.
"""

import sys
import os
import json
import requests
from lxml import html
from datetime import datetime
from typing import List, Optional, Callable, Dict
import boto3

# Configuration
S3_BUCKET = 'your-bucket-name'
S3_KEY = 'jobs_cache.json'
AWS_REGION = 'us-east-1'          # adjust as needed
EMAIL_SENDER = 'sender@example.com'
EMAIL_RECIPIENT = 'you@example.com'

# Initialize AWS clients
s3 = boto3.client('s3', region_name=AWS_REGION)
ses = boto3.client('ses', region_name=AWS_REGION)


# Standard browser-style UA
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

class JobItem:
    def __init__(self, title: str, link: str, team: Optional[str], date: Optional[str] = None):
        self.title = title
        self.link = link
        self.team = team
        self.date = date or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {"title": self.title, "link": self.link, "team": self.team, "date": self.date}

    @classmethod
    def from_dict(cls, data: Dict) -> 'JobItem':
        return cls(data['title'], data['link'], data.get('team'), data.get('date'))

    def __eq__(self, other):
        return isinstance(other, JobItem) and self.link == other.link

    def __hash__(self):
        return hash(self.link)

class JobList:
    def __init__(self, items: List[JobItem]):
        self.items = items

    @classmethod
    def load_s3(cls, bucket: str, key: str) -> 'JobList':
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(obj['Body'].read().decode())
            return cls([JobItem.from_dict(d) for d in data])
        except s3.exceptions.NoSuchKey:
            return cls([])

    def save_s3(self, bucket: str, key: str):
        s3.put_object(Bucket=bucket, Key=key, Body=json.dumps([i.to_dict() for i in self.items], indent=2).encode('utf-8'))


    def to_dict(self) -> List[Dict]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_dict(cls, data_list: List[Dict]) -> 'JobList':
        items = [JobItem.from_dict(d) for d in data_list]
        return cls(items)

    def save(self, filename: str):
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(filename: str) -> 'JobList':
        if not os.path.exists(filename):
            return JobList([])
        with open(filename) as f:
            data = json.load(f)
        return JobList.from_dict(data)

    def diff(self, other: 'JobList'):
        new = set(self.items) - set(other.items)
        removed = set(other.items) - set(self.items)
        return list(new), list(removed)


def scrape_dynamic(
    url: str,
    list_xpath: str,
    field_builders: Dict[str, Callable[[str], str]]
) -> JobList:
    """
    Fetch and parse the page, then build and return a JobList.
    """
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    tree = html.fromstring(resp.content)

    containers = tree.xpath(list_xpath)
    items: List[JobItem] = []

    for i, container in enumerate(containers, 1):
        x = str(i)
        fields = {}
        for name, build_xpath in field_builders.items():
            elems = container.xpath(build_xpath(x))
            if elems:
                first = elems[0]
                value = (
                    first.text_content().strip()
                    if hasattr(first, "text_content")
                    else str(first).strip()
                )
            else:
                value = None
            fields[name] = value
        items.append(JobItem(
            title=fields.get("title"),
            link="https://openai.com" + fields.get("link"),
            team=fields.get("team")
        ))

    return JobList(items)

def send_email(subject: str, body: str):
    ses.send_email(
        Source=EMAIL_SENDER,
        Destination={'ToAddresses': [EMAIL_RECIPIENT]},
        Message={
            'Subject': {'Data': subject},
            'Body': {'Text': {'Data': body}}
        }
    )

def main():
    URL = "https://openai.com/careers/search/?l=bbd9f7fe-aae5-476a-9108-f25aea8f6cd2&q=engineer"
    LIST_XPATH = '//*[@id="main"]/div[1]/div[2]/div/div'
    FIELD_BUILDERS = {
        "title": lambda x: ".//div/a[1]/div/h2",
        "link":  lambda x: ".//div/a[1]/@href",
        "team":  lambda x: ".//div/a[2]/div/span",
    }
    CACHE_FILE = 'jobs_cache.json'

    # Load existing
    existing_list = JobList.load_s3(S3_BUCKET, S3_KEY)

    # Scrape new
    scraped_list = scrape_dynamic(URL, LIST_XPATH, FIELD_BUILDERS)

    # Diff
    new_items, removed_items = scraped_list.diff(existing_list)
    if new_items:
        print("New items:")
        for item in new_items:
            print(f" + {item.title} ({item.link})")

    # Save updated cache
    # scraped_list.save_s3(CACHE_FILE)
    return new_items

def lambda_handler(event, context):
    # TODO implement
    items = main()
    return {
        'statusCode': 200,
        'body': json.dumps(items)
    }

if __name__ == "__main__":
    main()
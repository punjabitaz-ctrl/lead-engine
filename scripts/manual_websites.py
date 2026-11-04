#!/usr/bin/env python3
"""Manual website extraction from leads CSV.

Usage:
    python scripts/manual_websites.py --input campaigns/nj-dental/runs/leads-20261103-233528-b1.csv

This script generates search queries for finding websites manually,
then you can run them in Google and collect the URLs.
"""
import argparse
import pandas as pd
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Manual website extraction from leads')
    parser.add_argument('--input', required=True, help='Input CSV file')
    parser.add_argument('--output', default='extraction_tasks.md', help='Output tasks file')
    args = parser.parse_args()
    
    # Load leads
    df = pd.read_csv(args.input)
    
    with open(args.output, 'w') as f:
        f.write(f"# Manual Website Extraction Tasks\n")
        f.write(f"Generated from: {args.input}\n\n")
        f.write("## Instructions\n")
        f.write("1. Copy each search query into Google\n")
        f.write("2. Find the official website for that practice/company\n")
        f.write("3. Paste the URL in the provided box next to each company\n\n")
        
        # Group by city for efficiency
        cities = df['City'].unique()
        for city in sorted(cities):
            city_leads = df[df['City'] == city]
            f.write(f"### {city} ({len(city_leads)} leads)\n\n")
            
            for _, row in city_leads.iterrows():
                company = row['Company'] if pd.notna(row['Company']) else 'Unknown'
                specialty = row['Specialty'] if pd.notna(row['Specialty']) else ''
                phone = row['Phone'] if pd.notna(row['Phone']) else ''
                
                # Generate search query
                if specialty:
                    query = f"{company} website {specialty}"
                else:
                    query = f"{company} official website"
                
                f.write(f"- [ ] **{company}**\n")
                f.write(f"  - Specialty: {specialty if specialty else 'N/A'}\n")
                f.write(f"  - Phone: {phone if phone else 'N/A'}\n")
                f.write(f"  - Search: `{query}`\n")
                f.write(f"  - Website: _______________\n\n")
        
        f.write("---\n\n")
        f.write("## Tips\n")
        f.write("- Use quotes for exact company names: \"Company Name\"")
        f.write("- Add \"official website\" to search queries\n")
        f.write("- Try \"site:.com {company}\" to find their domain\n")

if __name__ == '__main__':
    main()

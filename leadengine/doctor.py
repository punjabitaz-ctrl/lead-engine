#!/usr/bin/env python3
"""
Doctor Command - Check Web Presence of Practices
================================================
Checks for websites, Google Business Profiles, and reviews using Google Places API.

Usage:
    python -m leadengine campaign doctor --input leads.csv --output results.csv

Requirements:
    - GOOGLE_PLACES_API_KEY environment variable (see docs/SETUP.md)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import requests

# Configuration
USE_GOOGLE_PLACES_API = os.environ.get("USE_GOOGLE_PLACES_API", "false").lower() == "true"
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if USE_GOOGLE_PLACES_API and not GOOGLE_PLACES_API_KEY:
    raise ValueError(
        "GOOGLE_PLACES_API_KEY not set but USE_GOOGLE_PLACES_API=true."
        " Set it in your environment or create a .env file with:
        GOOGLE_PLACES_API_KEY=your_key_here
        
        If you don't have an API key, use manual extraction mode instead:"
        " python -m leadengine campaign extract --campaign nj-dental"
    )
else:
    print("Note: Using manual extraction mode. Set USE_GOOGLE_PLACES_API=true for automated checking.")

BASE_URL = "https://places.googleapis.com/v1"


class GooglePlacesClient:
    """Client for Google Places API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
        }
        
        # Cache for previously looked up places
        self.cache_file = Path("data/places_cache.json")
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return {"places": {}, "cost_estimate": 0.0, "last_updated": None}
        
        try:
            with open(self.cache_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"places": {}, "cost_estimate": 0.0, "last_updated": None}
    
    def _save_cache(self):
        """Save cache to disk."""
        data = {
            "places": self.cache["places"],
            "cost_estimate": self.cache["cost_estimate"],
            "last_updated": datetime.now().isoformat()
        }
        with open(self.cache_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def search_places(self, query: str, location: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Search for places matching a query."""
        url = f"{BASE_URL}/places/search"
        
        params = {
            "query": query,
            "key": self.api_key
        }
        
        if location:
            params["locationRestriction"] = json.dumps({
                "circle": {
                    "center": location.get("center", [40.7128, -74.0060]),  # Default to NYC
                    "radius": location.get("radius", 50000)
                }
            })
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        results = response.json()
        return results.get("results", [])
    
    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """Get detailed information about a specific place."""
        url = f"{BASE_URL}/places/details"
        
        params = {
            "placeId": place_id,
            "key": self.api_key
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result.get("result")
    
    def check_presence(self, company: str, city: str, state: str) -> Dict[str, Any]:
        """Check for web presence of a business."""
        result = {
            "Company": company,
            "City": city,
            "State": state,
            "has_website": False,
            "has_gbp": False,
            "reviews_count": 0,
            "website_url": None,
            "google_profile_url": None,
            "rating": None,
            "search_time": datetime.now().isoformat()
        }
        
        # Create search query
        search_query = f"{company} {city}"
        
        # Check cache first
        cached = self.cache["places"].get(search_query)
        if cached:
            result.update(cached)
            return result
        
        # Search for the business
        places = self.search_places(search_query)
        
        if not places:
            self.cache["places"][search_query] = result
            self._save_cache()
            return result
        
        # Try to find exact match or best match
        for place in places:
            details = self.get_place_details(place["placeId"])
            
            if details:
                # Check for website
                website_field = details.get("website", {})
                if website_field and "value" in website_field:
                    result["has_website"] = True
                    result["website_url"] = website_field["value"]
                
                # Check for Google Business Profile
                if place.get("openingHours") or place.get("reviews"):
                    result["has_gbp"] = True
                    result["google_profile_url"] = place["name"]
                    
                    # Get review info
                    reviews = details.get("user_ratings_total", {})
                    if isinstance(reviews, dict):
                        rating_sum = reviews.get("ratingSum", 0)
                        user_rating_count = max(reviews.get("userRatingCount", 1), 1)
                        result["reviews_count"] = rating_sum / user_rating_count
                        result["rating"] = reviews.get("averageRating")
        
        # Cache the result
        self.cache["places"][search_query] = result
        
        # Estimate cost (approximately $0.035 per request for Text Search Enterprise)
        self.cache["cost_estimate"] += 0.035
        
        self._save_cache()
        
        return result


def run(input_file: str, output_file: str, max_concurrent: int, root: str = "campaigns") -> int:
    """Main entry point for doctor command."""
    # Load leads
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_file}")
        return 1
    
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} leads to check")
    
    # Create client and run checks
    client = GooglePlacesClient(GOOGLE_PLACES_API_KEY)
    results = []
    
    for _, row in df.iterrows():
        company = str(row.get("Company", "")).strip()
        city = str(row.get("City", "")).strip()
        state = str(row.get("State", "")).strip()
        
        if not company:
            continue
        
        print(f"Checking: {company} ({city}, {state})...")
        result = client.check_presence(company, city, state)
        results.append(result)
    
    # Save results
    output_df = pd.DataFrame(results)
    output_path = Path(output_file)
    output_df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_file}")
    
    # Summary
    has_website = sum(1 for r in results if r["has_website"])
    has_gbp = sum(1 for r in results if r["has_gbp"])
    
    print(f"\n=== SUMMARY ===")
    print(f"Total checked: {len(results)}")
    print(f"Websites found: {has_website}")
    print(f"GBP profiles: {has_gbp}")
    
    # Print cost estimate
    total_cost = client.cache["cost_estimate"]
    print(f"Estimated API cost: ${total_cost:.2f}")
    
    return 0


def check_website_with_manual_query(company: str, city: str, specialty: str) -> Dict[str, Any]:
    """Manually search for website using web search (returns placeholder for manual entry)."""
    result = {
        "Company": company,
        "City": city,
        "State": "",
        "has_website": False,
        "has_gbp": False,
        "reviews_count": 0,
        "website_url": None,
        "google_profile_url": None,
        "rating": None,
        "manual_search_query": f"{company} {city}",
        "specialty": specialty,
        "search_time": datetime.now().isoformat()
    }
    return result


def run(input_file: str, output_file: str, max_concurrent: int, root: str = "campaigns", 
        use_api: bool = False) -> int:
    """Main entry point for doctor command."""
    # Load leads
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_file}")
        return 1
    
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} leads to check")
    
    # Create client and run checks
    results = []
    
    for _, row in df.iterrows():
        company = str(row.get("Company", "")).strip()
        city = str(row.get("City", "")).strip()
        state = str(row.get("State", "")).strip()
        specialty = str(row.get("Specialty", "")).strip()
        
        if not company:
            continue
        
        print(f"Checking: {company} ({city}, {state})...", end=" -> ")
        
        if use_api and GOOGLE_PLACES_API_KEY:
            # Use Google Places API
            client = GooglePlacesClient(GOOGLE_PLACES_API_KEY)
            result = client.check_presence(company, city, state)
            results.append(result)
            print(f"API: {result.get('has_website', 'N/A')}")
        else:
            # Manual extraction mode
            result = check_website_with_manual_query(company, city, specialty)
            results.append(result)
            print("MANUAL_MODE")
    
    # Save results
    output_df = pd.DataFrame(results)
    output_path = Path(output_file)
    output_df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_file}")
    
    # Summary
    if use_api:
        has_website = sum(1 for r in results if r["has_website"])
        has_gbp = sum(1 for r in results if r["has_gbp"])
        total_cost = client.cache["cost_estimate"]
        print(f"\n=== SUMMARY ===")
        print(f"Total checked: {len(results)}")
        print(f"Websites found: {has_website}")
        print(f"GBP profiles: {has_gbp}")
        print(f"Estimated API cost: ${total_cost:.2f}")
    else:
        manual_count = sum(1 for r in results if "manual_search_query" in r)
        print(f"\n=== SUMMARY ===")
        print(f"Total checked: {len(results)}")
        print(f"Manual extraction mode - ready for manual website lookup")
        print(f"\n=== NEXT STEPS ===")
        print("1. Use the 'extract' command to generate search queries:")
        print(f"   python -m leadengine campaign extract --campaign {Path(input_file).parent.parent.name}")
        print("2. Manually find websites using Google")
        print("3. Update the CSV with found URLs")
    
    return 0


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check web presence of practices")
    parser.add_argument("--input", required=True, help="CSV file with leads")
    parser.add_argument("--output", default="presence_results.csv", help="Output CSV file")
    parser.add_argument("--max-concurrent", type=int, default=5, help="Max concurrent requests")
    parser.add_argument("--use-api", action="store_true", 
                        help="Use Google Places API (requires GOOGLE_PLACES_API_KEY env var)")
    
    args = parser.parse_args()
    
    sys.exit(run(args.input, args.output, args.max_concurrent, use_api=args.use_api))


if __name__ == "__main__":
    main()

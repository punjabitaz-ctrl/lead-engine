#!/usr/bin/env python3
"""
Google Places API Integration for Presence Checking
===================================================
Checks if practices have websites, Google Business Profiles, and reviews.

Usage:
    python -m leadengine doctor --presence-check places

Requirements:
    - GOOGLE_PLACES_API_KEY environment variable
    - Google Places API key configured in docs/SETUP.md
"""

import os
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime
import json

# Configuration
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
if not GOOGLE_PLACES_API_KEY:
    raise ValueError(
        "GOOGLE_PLACES_API_KEY not set. Set it in your environment or create"
        " a .env file with: GOOGLE_PLACES_API_KEY=your_key_here"
    )

BASE_URL = "https://places.googleapis.com/v1"


class GooglePlacesClient:
    """Client for Google Places API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "*"
        }
    
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
            "company": company,
            "city": city,
            "state": state,
            "has_website": False,
            "has_gbp": False,
            "reviews_count": 0,
            "website_url": None,
            "google_profile_url": None,
            "rating": None,
            "search_time": datetime.now().isoformat()
        }
        
        # Search for the business
        search_query = f"{company} {city}"
        places = self.search_places(search_query)
        
        if not places:
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
                    result["google_profile_url"] = f"https://www.google.com/maps/place/{place['placeId']}"
                    
                    # Get review info
                    reviews = details.get("user_ratings_total", {})
                    if isinstance(reviews, dict):
                        result["reviews_count"] = reviews.get("ratingSum", 0) / max(reviews.get("userRatingCount", 1), 1)
                        result["rating"] = reviews.get("averageRating")
        
        return result


def check_presence_batch(leads: List[Dict], client: GooglePlacesClient, max_concurrent: int = 5) -> List[Dict]:
    """Check presence for multiple leads concurrently."""
    results = []
    
    # Simple sequential implementation (could be enhanced with ThreadPoolExecutor)
    for lead in leads:
        result = client.check_presence(
            company=lead.get("Company", ""),
            city=lead.get("City", ""),
            state=lead.get("State", "")
        )
        results.append(result)
    
    return results


def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check web presence of practices")
    parser.add_argument("--input", required=True, help="CSV file with leads")
    parser.add_argument("--output", default="presence_results.csv", help="Output CSV file")
    parser.add_argument("--max-concurrent", type=int, default=5, help="Max concurrent requests")
    
    args = parser.parse_args()
    
    # Load leads
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} leads to check")
    
    # Create client and run checks
    client = GooglePlacesClient(GOOGLE_PLACES_API_KEY)
    results = check_presence_batch(df.to_dict('records'), client, args.max_concurrent)
    
    # Save results
    output_df = pd.DataFrame(results)
    output_df.to_csv(args.output, index=False)
    print(f"Results saved to {args.output}")
    
    # Summary
    has_website = sum(1 for r in results if r["has_website"])
    has_gbp = sum(1 for r in results if r["has_gbp"])
    print(f"
Summary:")
    print(f"  - Websites found: {has_website} / {len(results)}")
    print(f"  - GBP profiles: {has_gbp} / {len(results)}")


if __name__ == "__main__":
    main()

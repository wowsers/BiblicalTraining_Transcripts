import requests
import re
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://www.biblicaltraining.org"

def extract_course_slugs(page_url):
    """Extract bt_router_slug values from a Biblical Training page"""
    print(f"\n[+] Fetching: {page_url}")
    response = requests.get(page_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[!] Failed to fetch (Status: {response.status_code})")
        return []

    # Find all bt_router_slug patterns in the page
    slugs = re.findall(r'"bt_router_slug":"([^"]+)"', response.text)
    return list(set(slugs))  # Remove duplicates


def main():
    core_url = "https://www.biblicaltraining.org/programs/institute#tabs--core-classes"
    elective_url = "https://www.biblicaltraining.org/programs/institute#tabs--elective-classes"
    
    print("=" * 60)
    print("Extracting Course Slugs from Biblical Training")
    print("=" * 60)
    
    # Extract core and elective courses
    # Note: The URLs with anchors don't change content, so we fetch the base URL
    base_url = "https://www.biblicaltraining.org/programs/institute"
    slugs = extract_course_slugs(base_url)
    
    if not slugs:
        print("[!] No course slugs found. The page structure may have changed.")
        return
    
    # Build full course URLs
    print("\n[✔] Found course slugs:\n")
    print("# Full URLs for courses_to_run:")
    print("courses_to_run = [")
    
    for slug in sorted(slugs):
        full_url = f"https://www.biblicaltraining.org/learn/institute/{slug}"
        print(f'    "{full_url}",')
    
    print("]")
    
    print(f"\n[✔] Total courses found: {len(slugs)}")
    
    # Also save to a text file for easy copying
    with open("available_courses.txt", "w") as f:
        f.write("Available Course URLs (copy into courses_to_run):\n")
        f.write("=" * 60 + "\n\n")
        for slug in sorted(slugs):
            full_url = f"https://www.biblicaltraining.org/learn/institute/{slug}"
            f.write(f'"{full_url}",\n')
    
    print(f"\n[✔] Saved to: available_courses.txt")


if __name__ == "__main__":
    main()

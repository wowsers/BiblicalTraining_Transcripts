import requests
from bs4 import BeautifulSoup
import time
import re
import os

# =========================================================================
# CONFIGURATION: Put the MAIN course URL and Destination Path here
# =========================================================================
course_url = "https://www.biblicaltraining.org/learn/institute/exploring-old-testament-ot500"
base_url = "https://www.biblicaltraining.org"
output_dir = r"C:\Users\ryang\OneDrive\Documents\BiblicalTraining_Transcripts"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Ensure the targeted OneDrive directory exists
os.makedirs(output_dir, exist_ok=True)
course_id = course_url.split('/')[-1]

print(f"Step 1: Connecting to main course page...")
response = requests.get(course_url, headers=headers)
if response.status_code != 200:
    print(f"Error: Could not access the main page (Status Code: {response.status_code})")
    exit()

soup = BeautifulSoup(response.text, 'html.parser')

# =========================================================================
# Extract Main Course Meta Elements
# =========================================================================
print("Step 2: Pulling course stats and 'About This Class' profile...")

# 1. Grab Professor Name from the specific /professors/ link structure
professor_name = "Unknown Professor"
prof_link = soup.find('a', href=lambda x: x and '/professors/' in x)
if prof_link:
    professor_name = prof_link.get_text(strip=True)

# 2. Grab Course Stats Block (Lessons, Length, Format)
num_lessons = "Unknown"
total_length = "Unknown"
course_format = "Unknown"

for element in soup.find_all(['div', 'p', 'span', 'li']):
    text_content = element.get_text()
    if "Number of lessons:" in text_content:
        num_lessons = text_content.replace("Number of lessons:", "").strip()
    elif "Total length:" in text_content:
        total_length = text_content.replace("Total length:", "").strip()
    elif "Format:" in text_content:
        course_format = text_content.replace("Format:", "").strip()

# 3. Grab 'About This Class' narrative block
about_class_text = "No course description available."
about_heading = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4'] and "About This Class" in tag.text)
if about_heading:
    about_container = about_heading.find_next(['div', 'p'])
    if about_container:
        about_class_text = about_container.get_text(strip=True).replace("(less)", "").strip()

# =========================================================================
# Step 3: Discover Lesson Links
# =========================================================================
print("Step 3: Discovering individual lesson links...")
lesson_urls = []
seen_urls = set()

for a in soup.find_all('a', href=True):
    href = a['href']
    if course_id in href and href != course_url and not href.endswith(course_id):
        full_url = href if href.startswith('http') else base_url + href
        if full_url not in seen_urls:
            seen_urls.add(full_url)
            lesson_urls.append(full_url)

if not lesson_urls:
    print("No lesson links found! Check if the course URL format is correct.")
    exit()

print(f"Found {len(lesson_urls)} lessons to process.\n")

# =========================================================================
# Step 4: Loop and Scrape Each Lesson Page
# =========================================================================
all_lessons_data = []
course_name_global = "Course"
course_code_global = ""

for index, url in enumerate(lesson_urls, start=1):
    print(f"[{index}/{len(lesson_urls)}] Scraping: {url.split('/')[-1]}...")

    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"   Skipping... Failed to reach page (Status: {res.status_code})")
            continue

        lesson_soup = BeautifulSoup(res.text, 'html.parser')

        # 1. Extract Lesson Metadata
        course_code = lesson_soup.find('meta', {'name': 'course:code'})
        course_name = lesson_soup.find('meta', {'name': 'course:name'})
        lesson_num = lesson_soup.find('meta', {'name': 'course:lesson:number'})
        lesson_name = lesson_soup.find('meta', {'name': 'course:lesson:name'})

        c_code = course_code['content'] if course_code else ""
        c_name = course_name['content'] if course_name else "Unknown Course"
        l_num = lesson_num['content'] if lesson_num else str(index)
        l_name = lesson_name['content'] if lesson_name else "Unknown Lesson"

        if c_name != "Unknown Course":
            course_name_global = c_name
        if c_code:
            course_code_global = f"({c_code})"

        # 2. Extract Lesson Intro Summary
        lesson_intro_text = "No intro summary available."
        intro_heading = lesson_soup.find('h2', class_='h3')
        if intro_heading:
            intro_container = intro_heading.find_next('div', class_='formatted-text')
            if intro_container:
                lesson_intro_text = intro_container.get_text(strip=True)

        # 3. Extract and Format Outline
        formatted_outline_lines = []
        outline_container = lesson_soup.find('div', class_='bt-outline')
        if outline_container:
            for p in outline_container.find_all('p'):
                text = p.get_text(strip=True)
                classes = p.get('class', [])
                indent_class = classes[0] if classes else 'out-1'

                if indent_class == 'out-2':
                    indent = "    "
                elif indent_class == 'out-3':
                    indent = "        "
                else:
                    indent = ""
                formatted_outline_lines.append(f"{indent}{text}")
        formatted_outline = "\n".join(formatted_outline_lines) if formatted_outline_lines else "No outline available."

        # 4. Extract and Format Transcript
        transcript_paragraphs = []
        transcript_container = lesson_soup.find(id='class--transcription')
        if transcript_container:
            inner_text_container = transcript_container.find('div', class_='formatted-text')
            if inner_text_container:
                for p in inner_text_container.find_all('p'):
                    p_text = p.get_text(strip=True)
                    if p_text:
                        transcript_paragraphs.append(p_text)
        formatted_transcript = "\n\n".join(
            transcript_paragraphs) if transcript_paragraphs else "No transcript available."

        all_lessons_data.append({
            "number": l_num,
            "title": l_name,
            "intro": lesson_intro_text,
            "outline": formatted_outline,
            "transcript": formatted_transcript
        })

        time.sleep(1)

    except Exception as e:
        print(f"   Error scraping this lesson: {e}")

# =========================================================================
# Step 5: Assemble and Compile Master Markdown Document
# =========================================================================
print("\nStep 5: Writing all collected data to OneDrive file...")

try:
    all_lessons_data.sort(key=lambda x: int(x['number']))
except ValueError:
    pass

# Sanitize filename and construct total destination path
safe_filename = f"{course_name_global}_Transcripts.md"
safe_filename = re.sub(r'[\\/*?:"<>|]', "", safe_filename).replace(" ", "_")
full_destination_path = os.path.join(output_dir, safe_filename)

with open(full_destination_path, "w", encoding="utf-8") as f:
    # Global Course Card Layout Header
    f.write(f"# {course_name_global} {course_code_global}\n")
    f.write(f"**Instructor:** {professor_name}\n\n")

    f.write("### Course Details\n")
    f.write(f"* **Total Lessons:** {num_lessons}\n")
    f.write(f"* **Total Runtime:** {total_length}\n")
    f.write(f"* **Media Format:** {course_format}\n\n")

    f.write("### About This Class\n")
    f.write(f"{about_class_text}\n\n")
    f.write("---\n\n")

    # Table of Contents
    f.write("## Table of Contents / Lesson Index\n")
    for lesson in all_lessons_data:
        f.write(f"* [Lesson {lesson['number']}: {lesson['title']}](#lesson-{lesson['number']})\n")
    f.write("\n" + "=" * 80 + "\n\n")

    # Lesson Details Assembly
    for lesson in all_lessons_data:
        f.write(f"## <a name='lesson-{lesson['number']}'></a>Lesson {lesson['number']}: {lesson['title']}\n\n")

        f.write("### Lesson Summary Intro\n")
        f.write(f"{lesson['intro']}\n\n")

        # Changed from 'Course Outline' to 'Lesson Outline'
        f.write("### Lesson Outline\n")
        f.write(f"```\n{lesson['outline']}\n```\n\n")

        f.write("### Transcript\n")
        f.write(f"{lesson['transcript']}\n\n")

        f.write("---\n\n")

print(f"SUCCESS! All transcripts compiled into:\n{full_destination_path}")
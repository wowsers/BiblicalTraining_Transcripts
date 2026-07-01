import os
import re
import io
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


try:
    from pypdf import PdfWriter
    from pypdf.generic import (
        NameObject,
        DictionaryObject,
        NumberObject,
        RectangleObject,
        StreamObject,
    )
except ImportError:
    print("[!] Missing dependency: Please run 'pip install pypdf' in your terminal.")
    exit(1)

BASE_URL = "https://www.biblicaltraining.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _escape_pdf_text(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_text_stream(lines, font_name="/F1", font_size=14, x=72, y_start=720, line_height=24):
    stream_lines = ["BT", f"{font_name} {font_size} Tf", f"{x} {y_start} Td"]
    for index, line in enumerate(lines):
        if index > 0:
            stream_lines.append(f"0 -{line_height} Td")
        stream_lines.append(f"({_escape_pdf_text(line)}) Tj")
    stream_lines.append("ET")
    return "\n".join(stream_lines).encode("utf-8")


def _add_attachment_outline_page(writer, download_targets):
    page = writer.add_blank_page(width=612, height=792)
    resources = page.get(NameObject("/Resources"), DictionaryObject())
    fonts = resources.get(NameObject("/Font"), DictionaryObject())
    fonts[NameObject("/F1")] = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources

    lines = ["Merged Attachments Outline"]
    lines.append("")
    for idx, target in enumerate(download_targets, start=1):
        lines.append(f"{idx}. {target['name']}")

    content = StreamObject()
    page_content = _build_text_stream(lines, font_size=16 if len(lines) <= 10 else 14)
    content.set_data(page_content)
    content[NameObject("/Length")] = NumberObject(len(page_content))
    page[NameObject("/Contents")] = content

    for index, target in enumerate(download_targets, start=1):
        y = 720 - (index * 24)
        if y < 72:
            break
        rect = RectangleObject([72, y - 4, 540, y + 14])
        writer.add_uri(0, target["url"], rect)


def extract_course_resources_header(soup, attachment_pdf_name):
    """
    Extracts books and links to display at the top of the Markdown file.
    Lists the local merged attachments file right alongside the core details.
    """
    resources_md = ["## 📚 Course Resources & Materials\n"]
    download_urls = []

    # 1. Recommended Books
    books_heading = soup.find(lambda tag: tag.name == "h4" and "Recommended Books" in tag.text)
    if books_heading:
        resources_md.append("### Recommended Books")
        parent_div = books_heading.find_parent('div')
        if parent_div:
            for book_title_tag in parent_div.find_all('h3'):
                title = book_title_tag.text.strip()
                p_tag = book_title_tag.find_next('p')
                desc = p_tag.text.strip() if p_tag else "No description available."
                resources_md.append(f"* **{title}**: {desc}")
            resources_md.append("")

    # 2. Gather Download Links & Note the Local Merged Companion File
    dl_heading = soup.find(lambda tag: tag.name == "h4" and "Downloads" in tag.text)
    if dl_heading:
        resources_md.append("### Core Downloads")
        resources_md.append(
            f"📁 *All files listed below have been compiled into standard PDF:* `{attachment_pdf_name}`\n")
        parent_div = dl_heading.find_parent('div')
        if parent_div:
            for link in parent_div.find_all('a', href=True):
                name = link.text.strip()
                url = urljoin(BASE_URL, link['href'])
                resources_md.append(f"* {name} ([Original Live Link]({url}))")
                download_urls.append({"name": name, "url": url})
            resources_md.append("")

    # 3. Recommended Readings
    read_heading = soup.find(lambda tag: tag.name == "h4" and "Recommended Readings" in tag.text)
    if read_heading:
        resources_md.append("### Recommended Readings")
        parent_div = read_heading.find_parent('div')
        if parent_div:
            for link in parent_div.find_all('a', href=True):
                url = urljoin(BASE_URL, link['href'])
                resources_md.append(f"* [{link.text.strip()}]({url})")
            resources_md.append("")

    # 4. External Links
    links_heading = soup.find(lambda tag: tag.name == "h2" and "Links" in tag.text)
    if links_heading:
        resources_md.append("### Additional External Links")
        parent_div = links_heading.find_parent('div')
        if parent_div:
            for link in parent_div.find_all('a', href=True):
                resources_md.append(f"* [{link.text.strip()}]({link['href']})")
            resources_md.append("")

    return "\n".join(resources_md) + "\n---\n", download_urls


def download_and_merge_pdfs(download_targets, output_pdf_filepath):
    """
    Downloads all targeted companion PDFs, merges them sequentially,
    and builds a first page that lists the merged attachments.
    """
    print(f"[->] Initializing PDF Compilation Engine for {len(download_targets)} assets...")
    merger = PdfWriter()
    _add_attachment_outline_page(merger, download_targets)
    successful_appends = 0

    for target in download_targets:
        name = target["name"]
        url = target["url"]
        print(f"    [->] Downloading asset to memory: {name}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code == 200:
                pdf_stream = io.BytesIO(response.content)
                merger.append(pdf_stream, outline_item=name)
                successful_appends += 1
            else:
                print(f"    [!] Skipping asset '{name}': Server returned HTTP status {response.status_code}")
        except Exception as e:
            print(f"    [!] Error pulling asset '{name}': {str(e)}")

        time.sleep(1)

    if successful_appends > 0:
        with open(output_pdf_filepath, "wb") as f_out:
            merger.write(f_out)
        print(f"[✔] Merged PDF generated with interactive structural outlines: {os.path.basename(output_pdf_filepath)}")
    else:
        print("[!] No attachments were successfully compiled.")

    merger.close()


def _extract_course_metadata(soup):
    professor_name = "Unknown Professor"
    prof_link = soup.find('a', href=lambda x: x and '/professors/' in x)
    if prof_link:
        professor_name = prof_link.get_text(strip=True)

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

    about_class_text = "No course description available."
    about_heading = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4'] and "About This Class" in tag.text)
    if about_heading:
        about_container = about_heading.find_next(['div', 'p'])
        if about_container:
            about_class_text = about_container.get_text(strip=True).replace("(less)", "").strip()

    return professor_name, num_lessons, total_length, course_format, about_class_text


def _discover_lesson_links(soup, course_url):
    course_id = course_url.split('/')[-1]
    lesson_urls = []
    seen_urls = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        if course_id in href and href != course_url and not href.rstrip('/').endswith(course_id):
            full_url = href if href.startswith('http') else urljoin(BASE_URL, href)
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                lesson_urls.append(full_url)

    return lesson_urls


def _scrape_lesson_page(lesson_url, default_index):
    response = requests.get(lesson_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"    [!] Failed to fetch lesson page: {lesson_url} (Status: {response.status_code})")
        return None

    lesson_soup = BeautifulSoup(response.content, 'html.parser')

    course_code = lesson_soup.find('meta', {'name': 'course:code'})
    course_name = lesson_soup.find('meta', {'name': 'course:name'})
    lesson_num = lesson_soup.find('meta', {'name': 'course:lesson:number'})
    lesson_name = lesson_soup.find('meta', {'name': 'course:lesson:name'})

    l_num = lesson_num['content'] if lesson_num else str(default_index)
    l_name = lesson_name['content'] if lesson_name else lesson_soup.title.string.strip() if lesson_soup.title else f"Lesson {default_index}"

    lesson_intro_text = "No intro summary available."
    intro_heading = lesson_soup.find('h2', class_='h3') or lesson_soup.find('h2')
    if intro_heading:
        intro_container = intro_heading.find_next('div', class_='formatted-text')
        if intro_container:
            lesson_intro_text = intro_container.get_text(strip=True)

    outline_container = lesson_soup.find('div', class_='bt-outline')
    formatted_outline_lines = []
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

    transcript_paragraphs = []
    transcript_container = lesson_soup.find(id='class--transcription')
    if transcript_container:
        inner_text_container = transcript_container.find('div', class_='formatted-text')
        if inner_text_container:
            for p in inner_text_container.find_all('p'):
                p_text = p.get_text(strip=True)
                if p_text:
                    transcript_paragraphs.append(p_text)

    formatted_transcript = "\n\n".join(transcript_paragraphs) if transcript_paragraphs else "No transcript available."

    return {
        "number": l_num,
        "title": l_name,
        "intro": lesson_intro_text,
        "outline": formatted_outline,
        "transcript": formatted_transcript,
    }


def scrape_course(course_url, output_dir):
    """
    Scrapes a target course, downloads/merges attachment files into a clean format,
    and structures everything into your OneDrive folder.
    """
    print(f"\n[+] Starting Processing for: {course_url}")

    response = requests.get(course_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[!] Failed to fetch course page (Status: {response.status_code})")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    title_tag = soup.find('h1')
    course_title = title_tag.text.strip() if title_tag else course_url.split('/')[-1].replace('-', ' ').title()

    clean_md_name = re.sub(r'[\\/*?:"<>|]', "", course_title) + ".md"
    clean_pdf_base = re.sub(r'[^a-zA-Z0-9]', "", course_title)
    clean_pdf_name = f"{clean_pdf_base}Attachments.pdf"

    output_md_filepath = os.path.join(output_dir, clean_md_name)
    output_pdf_filepath = os.path.join(output_dir, clean_pdf_name)

    markdown_content = []
    markdown_content.append(f"# Course: {course_title}\n")
    markdown_content.append(f"**Source URL:** {course_url}\n")
    markdown_content.append("---\n")

    print("[->] Parsing metadata structures...")
    resource_header, download_targets = extract_course_resources_header(soup, clean_pdf_name)
    markdown_content.append(resource_header)

    # Course metadata and lesson scraping
    professor_name, num_lessons, total_length, course_format, about_class_text = _extract_course_metadata(soup)
    lesson_urls = _discover_lesson_links(soup, course_url)

    markdown_content.append("## 📝 Class Lessons & Transcripts\n")
    markdown_content.append("### Course Summary\n")
    markdown_content.append(f"* **Instructor:** {professor_name}\n")
    markdown_content.append(f"* **Total Lessons:** {num_lessons}\n")
    markdown_content.append(f"* **Total Runtime:** {total_length}\n")
    markdown_content.append(f"* **Media Format:** {course_format}\n\n")
    markdown_content.append("### About This Class\n")
    markdown_content.append(f"{about_class_text}\n\n")

    if lesson_urls:
        print(f"[->] Found {len(lesson_urls)} lesson pages for transcripts.")

    all_lessons_data = []
    for index, lesson_url in enumerate(lesson_urls, start=1):
        try:
            lesson_data = _scrape_lesson_page(lesson_url, index)
            if lesson_data:
                all_lessons_data.append(lesson_data)
        except Exception as e:
            print(f"    [!] Error scraping lesson {lesson_url}: {e}")
        time.sleep(1)

    try:
        all_lessons_data.sort(key=lambda x: int(x["number"]))
    except (ValueError, TypeError):
        pass

    markdown_content.append("## Lesson Index\n")
    if all_lessons_data:
        for lesson in all_lessons_data:
            markdown_content.append(f"* [Lesson {lesson['number']}: {lesson['title']}](#lesson-{lesson['number']})\n")
        markdown_content.append("\n---\n\n")

        for lesson in all_lessons_data:
            markdown_content.append(f"## <a name='lesson-{lesson['number']}'></a>Lesson {lesson['number']}: {lesson['title']}\n\n")
            markdown_content.append("### Lesson Summary Intro\n")
            markdown_content.append(f"{lesson['intro']}\n\n")
            markdown_content.append("### Lesson Outline\n")
            markdown_content.append("```\n")
            markdown_content.append(f"{lesson['outline']}\n")
            markdown_content.append("```\n\n")
            markdown_content.append("### Transcript\n")
            markdown_content.append(f"{lesson['transcript']}\n\n")
            markdown_content.append("---\n\n")
    else:
        markdown_content.append("No lesson transcripts were found for this course.\n")

    # Save the Markdown document
    with open(output_md_filepath, 'w', encoding='utf-8') as f:
        f.writelines(markdown_content)
    print(f"[✔] Compiled text index successfully: {clean_md_name}")

    # Process and Download PDF Attachments to a Single File if found
    if download_targets:
        download_and_merge_pdfs(download_targets, output_pdf_filepath)


if __name__ == "__main__":
    # Updated default workspace to your exact designated OneDrive directory
    output_directory = r"C:\Users\ryang\OneDrive\Documents\BiblicalTraining_Transcripts"
    os.makedirs(output_directory, exist_ok=True)

    courses_to_run = [
        "https://www.biblicaltraining.org/learn/institute/exploring-old-testament-ot500"
    ]

    for url in courses_to_run:
        try:
            scrape_course(url, output_directory)
            time.sleep(3)
        except Exception as e:
            print(f"[!] Critical Error handling course {url}: {str(e)}")

    print("\n[✔] Processing completed successfully.")
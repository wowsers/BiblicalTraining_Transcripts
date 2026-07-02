import os
import re
import io
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from pypdf import PdfWriter
from pypdf.generic import (
    NameObject,
    DictionaryObject,
    NumberObject,
    RectangleObject,
    StreamObject,
)

BASE_URL = "https://www.biblicaltraining.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _sanitize_filename(value: str) -> str:
    return re.sub(r"[\\/*?:\"<>|]", "", value).strip()


def _clean_paragraph(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _build_text_stream(lines, font_name="/F1", font_size=14, x=72, y_start=720, line_height=22):
    stream_lines = ["BT", f"{font_name} {font_size} Tf", f"{x} {y_start} Td"]
    for index, line in enumerate(lines):
        if index > 0:
            stream_lines.append(f"0 -{line_height} Td")
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"({escaped}) Tj")
    stream_lines.append("ET")
    return "\n".join(stream_lines).encode("utf-8")


def _add_attachment_outline_page(writer: PdfWriter, download_targets):
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

    lines = [
        "Merged Attachments Outline",
        "",
        "Click an item below to open its original download URL.",
        "",
    ]
    for idx, target in enumerate(download_targets, start=1):
        display_name = target.get("name") or target.get("url")
        lines.append(f"{idx}. {display_name}")

    content = StreamObject()
    page_content = _build_text_stream(lines, font_size=14, line_height=22)
    content.set_data(page_content)
    content[NameObject("/Length")] = NumberObject(len(page_content))
    page[NameObject("/Contents")] = content

    header_lines = 4
    y_start = 720 - header_lines * 22
    for index, target in enumerate(download_targets, start=1):
        y = y_start - ((index - 1) * 22)
        if y < 72:
            break
        rect = RectangleObject([72, y - 4, 540, y + 16])
        writer.add_uri(0, target["url"], rect)


def extract_course_resources_header(soup, attachment_pdf_name):
    resources_md = ["## 📚 Course Resources & Materials\n"]
    download_urls = []

    books_heading = soup.find(lambda tag: tag.name == "h4" and "Recommended Books" in tag.text)
    if books_heading:
        resources_md.append("### Recommended Books")
        parent_div = books_heading.find_parent('div')
        if parent_div:
            for book_title_tag in parent_div.find_all('h3'):
                title = _clean_paragraph(book_title_tag.get_text())
                p_tag = book_title_tag.find_next('p')
                desc = _clean_paragraph(p_tag.get_text()) if p_tag else "No description available."
                resources_md.append(f"* **{title}**: {desc}")
            resources_md.append("")

    dl_heading = soup.find(lambda tag: tag.name == "h4" and "Downloads" in tag.text)
    if dl_heading:
        resources_md.append("### Core Downloads")
        resources_md.append(f"📁 *All files below have been combined to this PDF:* `{attachment_pdf_name}`\n")
        parent_div = dl_heading.find_parent('div')
        if parent_div:
            for link in parent_div.find_all('a', href=True):
                name = _clean_paragraph(link.get_text())
                if not name:
                    name = _clean_paragraph(link.get('aria-label') or link.get('title') or link['href'].split('/')[-1].replace('-', ' '))
                url = urljoin(BASE_URL, link['href'])
                if url and name:
                    resources_md.append(f"* {name} ([Original Live Link]({url}))")
                    download_urls.append({"name": name, "url": url})
                elif url:
                    resources_md.append(f"* [Download File]({url})")
                    download_urls.append({"name": url, "url": url})
            resources_md.append("")

    read_heading = soup.find(lambda tag: tag.name == "h4" and "Recommended Readings" in tag.text)
    if read_heading:
        resources_md.append("### Recommended Readings")
        parent_div = read_heading.find_parent('div')
        if parent_div:
            for link in parent_div.find_all('a', href=True):
                url = urljoin(BASE_URL, link['href'])
                resources_md.append(f"* [{_clean_paragraph(link.get_text())}]({url})")
            resources_md.append("")

    links_heading = soup.find(lambda tag: tag.name == "h2" and "Links" in tag.text)
    if links_heading:
        resources_md.append("### Additional External Links")
        parent_div = links_heading.find_parent('div')
        if parent_div:
            for link in parent_div.find_all('a', href=True):
                resources_md.append(f"* [{_clean_paragraph(link.get_text())}]({link['href']})")
            resources_md.append("")

    return "\n".join(resources_md) + "\n---\n", download_urls


def _extract_course_metadata(soup):
    professor_name = "Unknown Professor"
    prof_link = soup.find('a', href=lambda x: x and '/professors/' in x)
    if prof_link:
        professor_name = _clean_paragraph(prof_link.get_text())

    num_lessons = "Unknown"
    total_length = "Unknown"
    course_format = "Unknown"

    for element in soup.find_all(['div', 'p', 'span', 'li']):
        text_content = element.get_text()
        if "Number of lessons:" in text_content:
            num_lessons = _clean_paragraph(text_content.replace("Number of lessons:", ""))
        elif "Total length:" in text_content:
            total_length = _clean_paragraph(text_content.replace("Total length:", ""))
        elif "Format:" in text_content:
            course_format = _clean_paragraph(text_content.replace("Format:", ""))

    about_class_text = "No course description available."
    about_heading = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4'] and "About This Class" in tag.text)
    if about_heading:
        about_container = about_heading.find_next(['div', 'p'])
        if about_container:
            about_class_text = _clean_paragraph(about_container.get_text().replace("(less)", ""))

    return professor_name, num_lessons, total_length, course_format, about_class_text


def _discover_lesson_links(soup, course_url):
    course_id = course_url.rstrip('/').split('/')[-1]
    lesson_urls = []
    seen_urls = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        if course_id not in href:
            continue
        full_url = href if href.startswith('http') else urljoin(BASE_URL, href)
        if full_url == course_url or full_url.rstrip('/') == course_url.rstrip('/'):
            continue
        if full_url.startswith(BASE_URL) and full_url not in seen_urls:
            seen_urls.add(full_url)
            lesson_urls.append(full_url)

    return lesson_urls


def _format_outline(outline_container):
    if not outline_container:
        return "No outline available."

    lines = []
    for p in outline_container.find_all('p'):
        text = _clean_paragraph(p.get_text())
        classes = p.get('class', [])
        indent_class = classes[0] if classes else ''
        if indent_class == 'out-2':
            lines.append(f"  - {text}")
        elif indent_class == 'out-3':
            lines.append(f"    - {text}")
        else:
            lines.append(f"- {text}")

    return "\n".join(lines) if lines else "No outline available."


def _scrape_lesson_page(lesson_url, default_index):
    response = requests.get(lesson_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"    [!] Failed to fetch lesson page: {lesson_url} (Status: {response.status_code})")
        return None

    lesson_soup = BeautifulSoup(response.content, 'html.parser')
    lesson_num = lesson_soup.find('meta', {'name': 'course:lesson:number'})
    lesson_name = lesson_soup.find('meta', {'name': 'course:lesson:name'})

    l_num = lesson_num['content'] if lesson_num else str(default_index)
    l_name = lesson_name['content'] if lesson_name else _clean_paragraph(lesson_soup.title.string if lesson_soup.title else f"Lesson {default_index}")

    lesson_intro_text = "No intro summary available."
    intro_heading = lesson_soup.find('h2', class_='h3') or lesson_soup.find('h2')
    if intro_heading:
        intro_container = intro_heading.find_next('div', class_='formatted-text')
        if intro_container:
            lesson_intro_text = _clean_paragraph(intro_container.get_text())

    outline_container = lesson_soup.find('div', class_='bt-outline')
    formatted_outline = _format_outline(outline_container)

    transcript_paragraphs = []
    transcript_container = lesson_soup.find(id='class--transcription')
    if transcript_container:
        inner_text_container = transcript_container.find('div', class_='formatted-text')
        if inner_text_container:
            for p in inner_text_container.find_all('p'):
                p_text = _clean_paragraph(p.get_text())
                if p_text:
                    transcript_paragraphs.append(p_text)

    formatted_transcript = "\n\n".join(transcript_paragraphs) if transcript_paragraphs else "No transcript available."

    return {
        "number": l_num,
        "title": l_name,
        "intro": lesson_intro_text,
        "outline": formatted_outline,
        "transcript": formatted_transcript,
        "url": lesson_url,
    }


def download_and_merge_pdfs(download_targets, output_pdf_filepath):
    print(f"[->] Initializing PDF Compilation Engine for {len(download_targets)} assets...")
    writer = PdfWriter()
    _add_attachment_outline_page(writer, download_targets)
    successful_appends = 0

    for target in download_targets:
        name = target["name"]
        url = target["url"]
        print(f"    [->] Downloading asset to memory: {name}...")
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code == 200:
            pdf_stream = io.BytesIO(response.content)
            writer.append(pdf_stream, outline_item=name)
            successful_appends += 1
        else:
            print(f"    [!] Skipping asset '{name}': Server returned HTTP status {response.status_code}")
        time.sleep(1)

    if successful_appends > 0:
        with open(output_pdf_filepath, "wb") as f_out:
            writer.write(f_out)
        print(f"[✔] Merged PDF generated with interactive structural outlines: {os.path.basename(output_pdf_filepath)}")
    else:
        print("[!] No attachments were successfully compiled.")


def _write_markdown(course_title, course_url, metadata, resources_md, lessons, output_md_filepath, course_code=""):
    professor_name, num_lessons, total_length, course_format, about_class_text = metadata

    lines = [
        f"# {course_title}",
    ]
    if course_code:
        lines.append(f"**Course Code:** {course_code}")
    lines.extend([
        "",
        f"**Source URL:** {course_url}",
        "",
        "---",
        "",
        resources_md,
        "",
        "## 📝 Course Transcripts for Notebook LLM",
        "",
        "### Course Summary",
        f"* **Instructor:** {professor_name}",
        f"* **Total Lessons:** {num_lessons}",
        f"* **Total Runtime:** {total_length}",
        f"* **Media Format:** {course_format}",
        "",
        "### About This Class",
        about_class_text,
        "",
        "## Lesson Index",
    ])

    if lessons:
        for lesson in lessons:
            lines.append(f"* [Lesson {lesson['number']}: {lesson['title']}](#lesson-{lesson['number']})")
    else:
        lines.append("No lesson transcripts were found for this course.")

    lines.extend([
        "",
        "---",
        "",
    ])

    for lesson in lessons:
        lines.extend([
            f"## <a name='lesson-{lesson['number']}'></a>Lesson {lesson['number']}: {lesson['title']}",
            "",
            f"**Source URL:** {lesson['url']}",
            "",
            "### Lesson Summary Intro",
            lesson['intro'],
            "",
            "### Lesson Outline",
            lesson['outline'],
            "",
            "### Transcript",
            lesson['transcript'],
            "",
            "---",
            "",
        ])

    with open(output_md_filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines).strip() + "\n")


def scrape_course(course_url, output_dir):
    print(f"\n[+] Starting Processing for: {course_url}")
    response = requests.get(course_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[!] Failed to fetch course page (Status: {response.status_code})")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    title_tag = soup.find('h1')
    course_title = _sanitize_filename(title_tag.get_text(strip=True) if title_tag else course_url.split('/')[-1].replace('-', ' ').title())
    
    # Extract course code from URL (e.g., "ot500" from the end of the URL)
    course_code = course_url.rstrip('/').split('-')[-1].upper() if '-' in course_url.rstrip('/').split('/')[-1] else ""

    if course_code:
        clean_pdf_name = f"{course_title}_{course_code}_Attachments.pdf"
        output_md_filepath = os.path.join(output_dir, f"{course_title}_{course_code}_Notebook.md")
    else:
        clean_pdf_name = f"{course_title}_Attachments.pdf"
        output_md_filepath = os.path.join(output_dir, f"{course_title}_Notebook.md")
    output_pdf_filepath = os.path.join(output_dir, clean_pdf_name)

    metadata = _extract_course_metadata(soup)
    resource_header, download_targets = extract_course_resources_header(soup, clean_pdf_name)
    lesson_urls = _discover_lesson_links(soup, course_url)

    lessons = []
    for index, lesson_url in enumerate(lesson_urls, start=1):
        lesson_data = _scrape_lesson_page(lesson_url, index)
        if lesson_data:
            lessons.append(lesson_data)
        time.sleep(1)

    try:
        lessons.sort(key=lambda x: int(x['number']))
    except (ValueError, TypeError):
        pass

    _write_markdown(course_title, course_url, metadata, resource_header, lessons, output_md_filepath, course_code)
    print(f"[✔] Notebook-ready Markdown saved: {output_md_filepath}")

    if download_targets:
        download_and_merge_pdfs(download_targets, output_pdf_filepath)


if __name__ == '__main__':
    output_directory = r"C:\Users\ryang\OneDrive\Documents\BiblicalTraining_Transcripts"
    os.makedirs(output_directory, exist_ok=True)

    courses_to_run = [
        "https://www.biblicaltraining.org/learn/institute/exploring-old-testament-ot500",
        "https://www.biblicaltraining.org/learn/institute/bs600-listen-to-the-land-biblical-geography"
    ]

    for url in courses_to_run:
        try:
            scrape_course(url, output_directory)
            time.sleep(3)
        except Exception as e:
            print(f"[!] Critical Error handling course {url}: {str(e)}")

    print("\n[✔] Processing completed successfully.")
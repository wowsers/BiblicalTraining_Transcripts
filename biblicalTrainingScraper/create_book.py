import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# --- CONFIGURATION ---
SOURCE_FOLDER = "transcripts_exodus"
FINAL_PDF_NAME = "Exodus_Study_Guide.pdf"
OVERVIEW_FILE = "Lesson_00_Overview.txt"


class StudyGuidePDF(FPDF):
    def header(self):
        # Header starts after the Title and TOC pages
        if self.page_no() > 4:
            self.set_font("helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, "Deuteronomy: Complete Course Transcripts",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def clean_for_pdf(text):
    """Replaces Unicode characters to prevent encoding errors."""
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': "-", '\u2014': "-", '\u00a0': " ", '\u2026': "..."
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('latin-1', 'ignore').decode('latin-1')


def get_dynamic_outline(path):
    """Extracts Lesson Numbers, Titles, and Descriptions from the Overview."""
    outline = {}
    if not os.path.exists(path): return outline
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if "Lessons" in text:
        lesson_section = text.split("Lessons", 1)[1]
        pattern = r"(\d+)\.\s*([^\n]+)\n(.*?)(?=\n\d+\.|\Z)"
        matches = re.findall(pattern, lesson_section, re.DOTALL)
        for num, title, desc in matches:
            clean_num = num.zfill(2)
            outline[clean_num] = {
                "title": clean_for_pdf(title.strip()),
                "description": clean_for_pdf(desc.strip().replace('\n', ' '))
            }
    return outline


def generate_study_guide():
    # Diagnostic prints
    print(f"Looking in folder: {os.path.abspath(SOURCE_FOLDER)}")
    if not os.path.exists(SOURCE_FOLDER):
        print(f"ERROR: Folder '{SOURCE_FOLDER}' not found!")
        return

    overview_path = os.path.join(SOURCE_FOLDER, OVERVIEW_FILE)
    lesson_map = get_dynamic_outline(overview_path)
    files = sorted([f for f in os.listdir(SOURCE_FOLDER) if f.endswith(".txt") and "00" not in f])

    if not files:
        print("ERROR: No .txt files found in the source folder!")
        return

    pdf = StudyGuidePDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- 1. TITLE PAGE ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 26)
    pdf.set_y(80)
    pdf.cell(0, 20, "DEUTERONOMY", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 16)
    pdf.cell(0, 10, "The Gospel According to Moses", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 12)
    pdf.cell(0, 10, "Professor: Dr. Daniel Block", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- 2. PREPARE TOC PAGES (Placeholders) ---
    toc_start_page = pdf.page_no() + 1
    for _ in range(4):  # 4 pages for TOC to be safe
        pdf.add_page()

    lesson_page_info = {}

    # --- 3. TRANSCRIPT CHAPTERS ---
    for filename in files:
        lesson_num = "".join(filter(str.isdigit, filename)).zfill(2)
        title_data = lesson_map.get(lesson_num, {"title": f"Lesson {lesson_num}", "description": ""})

        path = os.path.join(SOURCE_FOLDER, filename)
        with open(path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # CLEANING LOGIC: Strip Navigation Header
        if "Daniel Block" in raw_content:
            content = raw_content.split("Daniel Block")[-1]
        elif "Deuteronomy" in raw_content:
            content = raw_content.split("Deuteronomy")[-1]
        else:
            content = raw_content

        # Strip Footer
        for marker in ["Class Resources", "About BiblicalTraining", "Lessons", "Scroll Down"]:
            if marker in content:
                content = content.split(marker)[0]

        content = clean_for_pdf(content.strip())

        pdf.add_page()
        lesson_page_info[lesson_num] = pdf.page_no()

        # Heading
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, f"LESSON {lesson_num}: {title_data['title'].upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
        pdf.ln(10)

        pdf.set_font("times", "", 11)
        pdf.multi_cell(0, 6, content)
        print(f"   Processed: Lesson {lesson_num}")

    # --- 4. BACKFILL TABLE OF CONTENTS ---
    pdf.page = toc_start_page
    pdf.set_y(20)
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 15, "Table of Contents", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    for num in sorted(lesson_map.keys()):
        dest_page = lesson_page_info.get(num)
        if dest_page:
            data = lesson_map[num]
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(0, 0, 255)
            link = pdf.add_link()
            pdf.set_link(link, page=dest_page)
            pdf.cell(0, 7, f"Lesson {num}: {data['title']} (p. {dest_page})",
                     link=link, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", "I", 9)
            pdf.multi_cell(0, 5, data['description'])
            pdf.ln(2)

    pdf.output(FINAL_PDF_NAME)
    print(f"\nSUCCESS: '{FINAL_PDF_NAME}' saved in {os.getcwd()}")


if __name__ == "__main__":
    generate_study_guide()
import sqlite3
from dateutil import parser
import pdfplumber
import os
pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]
if not pdf_files:
    print("No PDF file found in this folder. Please place your groundwater PDF here.")
    exit()
if len(pdf_files) == 1:
    PDF_PATH = pdf_files[0]
else:
    print("Multiple PDFs found in this folder:")
    for i, f in enumerate(pdf_files, start=1):
        print(f"{i}. {f}")
    choice = input("Enter the number of the PDF to process: ").strip()
    try:
        PDF_PATH = pdf_files[int(choice)-1]
    except:
        print("Invalid choice. Exiting.")
        exit()
print(f"Using PDF file: {PDF_PATH}")
DB_FILE = "groundwater.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS groundwater_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    measurement_type TEXT NOT NULL,
    value REAL NOT NULL,
    date TEXT NOT NULL
)
''')
conn.commit()
def parse_pdf_to_db(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            table = page.extract_table()
            if not table:
                print(f"No table found on page {page_num}")
                continue
            headers = table[0]  
            for row_num, row in enumerate(table[1:], start=1):
                try:
                    location = row[0].strip()
                    measurement_type = row[1].strip()
                    value = float(row[2])
                    date = parser.parse(row[3]).date().isoformat()

                    cursor.execute('''
                        INSERT INTO groundwater_data (location, measurement_type, value, date)
                        VALUES (?, ?, ?, ?)
                    ''', (location, measurement_type, value, date))
                except Exception as e:
                    print(f"Skipping row {row_num} on page {page_num}: {e}")

    conn.commit()
    print(f"PDF data inserted into SQLite database successfully into {DB_FILE}!")
parse_pdf_to_db(PDF_PATH)
conn.close()
"""Build the official-form report DOCX. Export its PDF using LibreOffice or Word."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('build_official_form_report.py')),run_name='__main__')

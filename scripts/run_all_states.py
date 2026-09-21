"""
Batch-process a folder of IIPS NFHS-6 State & District Fact Sheet Compendium
PDFs in one go: converts each to layout text, auto-detects the state/UT
name from the PDF's own title page (so you don't have to type it correctly
for every file), runs the extraction parser, and writes:

  - one CSV per state/UT into the output folder
  - one combined CSV with every state/UT processed so far
  - a summary table printed to the screen with a quick sanity check per
    state (district count, cascade-indicator coverage) so you can spot a
    state that likely needs closer attention, same as we've done manually
    for each state so far.

This does NOT replace the full validation checks (duplicate check,
row-count uniformity, TOC cross-check) - it's a fast first-pass signal.
Run those separately for anything this summary flags as suspicious.

Requires `pdftotext` (poppler) to be installed and on your PATH.

Usage:
    python run_all_states.py <folder_with_pdfs> [output_folder]

    If output_folder is omitted, defaults to ./data
"""
import csv
import glob
import os
import re
import subprocess
import sys

from extract_nfhs6 import parse_state_file

TITLE_BLOCK_RE = re.compile(
    r'KEY INDICATORS OF STATE AND DISTRICTS\s*\n+\s*(?P<state>[A-Z][A-Z &]+?)\s*\n'
)
BARE_HEADER_RE = re.compile(r'^\s*(?P<name>[A-Za-z][A-Za-z &]+?)\s*-\s*Key Indicators\s*$')


def detect_state_name(text):
    """Find the state/UT name from the PDF's own title page. Falls back to
    the most frequent bare '<Name> - Key Indicators' header if the title
    page pattern isn't found."""
    m = TITLE_BLOCK_RE.search(text)
    if m:
        return m.group('state').strip().title()

    counts = {}
    for line in text.splitlines():
        m = BARE_HEADER_RE.match(line.strip())
        if m:
            name = m.group('name').strip()
            counts[name] = counts.get(name, 0) + 1
    if counts:
        return max(counts, key=counts.get).title()
    return None


def pdf_to_layout_text(pdf_path, tmp_txt_path):
    result = subprocess.run(
        ['pdftotext', '-layout', pdf_path, tmp_txt_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr.strip()}")


def quick_check(rows, state_name):
    districts = set(r['district'] for r in rows)
    anc = set(); ib = set(); pnc = set()
    for r in rows:
        ind = r['indicator']
        if 'at least 4 antenatal care visits' in ind:
            anc.add(r['district'])
        elif ind.strip() == 'Institutional births (%)':
            ib.add(r['district'])
        elif 'Mothers who received postnatal care' in ind:
            pnc.add(r['district'])
    n = len(districts)
    coverage = 0.0
    if n:
        coverage = (len(anc) + len(ib) + len(pnc)) / (3 * n) * 100
    return n, len(rows), round(coverage, 1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_all_states.py <folder_with_pdfs> [output_folder]")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else 'data'
    os.makedirs(output_folder, exist_ok=True)

    pdf_paths = sorted(glob.glob(os.path.join(input_folder, '*.pdf')))
    if not pdf_paths:
        print(f"No PDF files found in {input_folder}")
        sys.exit(1)

    combined_rows = []
    summary = []

    for pdf_path in pdf_paths:
        fname = os.path.basename(pdf_path)
        tmp_txt = os.path.join(output_folder, '_tmp_layout.txt')
        try:
            pdf_to_layout_text(pdf_path, tmp_txt)
            with open(tmp_txt, encoding='utf-8', errors='replace') as f:
                text = f.read()
            state_name = detect_state_name(text)
            if not state_name:
                summary.append((fname, 'FAILED', 'could not detect state name', '', ''))
                continue

            rows = parse_state_file(tmp_txt, state_name)
            if not rows:
                summary.append((fname, state_name, '0 rows extracted - needs review', '', ''))
                continue

            out_csv = os.path.join(
                output_folder, state_name.lower().replace(' ', '_') + '_nfhs6_district.csv'
            )
            with open(out_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'state', 'district', 'category', 'indicator_no', 'indicator',
                    'nfhs6_value', 'nfhs5_value', 'small_sample_flag', 'boundary_change_single_round'
                ])
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)

            combined_rows.extend(rows)
            n_districts, n_rows, coverage = quick_check(rows, state_name)
            flag = 'OK' if coverage == 100.0 else f'CHECK ({coverage}% cascade coverage)'
            summary.append((fname, state_name, str(n_districts) + ' districts', str(n_rows) + ' rows', flag))

        except Exception as e:
            summary.append((fname, 'ERROR', str(e), '', ''))
        finally:
            if os.path.exists(tmp_txt):
                os.remove(tmp_txt)

    if combined_rows:
        combined_path = os.path.join(output_folder, 'all_states_nfhs6_district.csv')
        with open(combined_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'state', 'district', 'category', 'indicator_no', 'indicator',
                'nfhs6_value', 'nfhs5_value', 'small_sample_flag', 'boundary_change_single_round'
            ])
            writer.writeheader()
            for r in combined_rows:
                writer.writerow(r)

    print(f"\n{'File':<45} {'State detected':<18} {'Districts/Rows':<18} {'Status'}")
    print('-' * 100)
    for fname, state, col3, col4, status in summary:
        print(f"{fname:<45} {state:<18} {col3:<10} {col4:<10} {status}")
    print(f"\nProcessed {len(pdf_paths)} PDF(s). Combined output: "
          f"{os.path.join(output_folder, 'all_states_nfhs6_district.csv')}")
    print("Note: this is a quick first-pass check only. Run the full validation "
          "(duplicate check, row-count uniformity, TOC cross-check) on anything "
          "flagged CHECK or ERROR above, and spot-check a few OK states too.")


if __name__ == '__main__':
    main()

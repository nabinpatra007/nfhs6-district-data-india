"""
Extract district-level indicators from IIPS NFHS-6 State & District Fact
Sheet Compendium PDFs (pdftotext -layout output).

Two document layouts are handled:

1. Multi-district states/UTs: one 4-column state-level summary table
   (Urban/Rural/NFHS-6 Total/NFHS-5 Total), titled "<State> - Key
   Indicators" - SKIPPED - followed by one 2-column table per district,
   titled "<District>, <State> - Key Indicators".

2. Single-district Union Territories (e.g. Chandigarh): there is no
   separate district breakdown at all. The only table is the same
   4-column "<UT> - Key Indicators" table that would normally be the
   skipped state summary elsewhere - here it IS the data, and is treated
   as that UT's sole "district" (named after the UT itself). Detected by
   pre-scanning the file for any genuine "<District>, <State> - Key
   Indicators" header; if none exists, the file is assumed single-district.

Value columns per indicator line can be:
  - 2 values: NFHS-6 Total, NFHS-5 Total (standard district table)
  - 1 value: NFHS-6 Total only (district with a boundary change since
    NFHS-5, so no comparable prior-round figure)
  - 4 values: Urban, Rural, NFHS-6 Total, NFHS-5 Total (state/UT-level
    table) - only the last two (the Total columns) are kept, for schema
    consistency with district-level rows.

Handles three line layouts for an indicator entry:
  1. Single line: "NN. <full text>   <value(s)>"
  2. Wrapped (long indicator names): the number+text-start line carries no
     values, the *next* line holds only the value(s) (possibly combined
     with leftover wrapped text), and further line(s) may carry more
     wrapped text with no values at all.

Usage: python extract_nfhs6.py <layout.txt> <state_name> > output.csv
"""
import re
import sys
import csv

# Matches a genuine district block header: "<District>, <State> - Key Indicators"
DISTRICT_HEADER_RE = re.compile(r'^(?P<name>.+?),\s*[\w\s]+?\s*-\s*Key Indicators\s*$')

# Matches a bare "<Name> - Key Indicators" header with NO comma - this is
# either the (skippable) state-level summary in a multi-district file, or
# the sole table in a single-district UT file. Which one it is gets
# resolved by the pre-scan in parse_state_file().
BARE_HEADER_RE = re.compile(r'^(?P<name>.+?)\s*-\s*Key Indicators\s*$')

# Matches a category/section header. These lines sometimes carry the
# repeated "Total  Total" (or single "Total", or "Urban Rural Total Total")
# column sub-header text at the end, produced when a category happens to
# fall at the top of a new page in the layout-extracted text - that
# trailing part is stripped, not treated as part of the category name.
# Digits are allowed (e.g. "age 15-49 years").
CATEGORY_LINE_RE = re.compile(
    r'^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/&\-]*?)'
    r'(?:\s{2,}(?:Urban\s{2,}Rural\s{2,})?Total(?:\s{2,}Total)?)?\s*$'
)

VALUE_TOKEN = r'(?:\*|\(?\d[\d,\.]*\)?)'
# A run of 1 to 4 whitespace-separated value tokens, captured as one group
# and split apart in Python (simpler and more robust than trying to
# distinguish 1-, 2-, and 4-column cases with separate regexes).
VALUES_RUN = r'(?P<vals>' + VALUE_TOKEN + r'(?:\s+' + VALUE_TOKEN + r'){0,3})'

INDICATOR_RE = re.compile(
    r'^\s*(?P<num>\d{1,3})\.\s*(?P<text>.+?)\s{2,}' + VALUES_RUN + r'\s*$'
)
# Start of a wrapped entry: number + text, but NOT followed by a value
# (falls through here only because INDICATOR_RE already failed)
INDICATOR_START_RE = re.compile(r'^\s*(?P<num>\d{1,3})\.\s*(?P<text>.+)$')

# A line holding only the value(s) for a wrapped entry (right-aligned, no text)
VALUES_ONLY_RE = re.compile(r'^\s*' + VALUES_RUN + r'\s*$')

# A continuation line carrying BOTH leftover wrapped text AND the trailing
# values together, e.g. "    days of delivery+ (%)   66.5   46.4"
CONTINUATION_VALUES_RE = re.compile(
    r'^\s*(?P<text>\S.*?)\s{2,}' + VALUES_RUN + r'\s*$'
)


def _split_values(vals_str):
    """Split a matched value-run into (nfhs6, nfhs5, boundary_change).
    Only the last two tokens (the Total/Total columns) are kept - a 4-token
    match (Urban/Rural/Total/Total) discards the first two."""
    tokens = vals_str.split()
    if len(tokens) == 1:
        return tokens[0], None, True
    # 2 or 4 tokens: last two are always the NFHS-6 Total / NFHS-5 Total columns
    return tokens[-2], tokens[-1], False


def _emit(rows, state_name, district, category, num, text, vals_str):
    nfhs6, nfhs5, boundary_change = _split_values(vals_str)
    # IIPS flags a suppressed/small-sample figure two ways in the source PDF:
    #   ( )  = based on 25-49 unweighted cases
    #   *    = based on fewer than 25 unweighted cases (value not shown)
    # Both are captured here, not just the parenthesized case.
    def _is_small_sample(v):
        return v is not None and ('(' in v or v == '*')
    flagged = _is_small_sample(nfhs6) or _is_small_sample(nfhs5)
    rows.append({
        'state': state_name,
        'district': district,
        'category': category or '',
        'indicator_no': num,
        'indicator': text.strip(),
        'nfhs6_value': nfhs6.strip('()'),
        'nfhs5_value': nfhs5.strip('()') if nfhs5 else '',
        'small_sample_flag': flagged,
        'boundary_change_single_round': boundary_change,
    })


def _is_multi_district(lines, state_name):
    """Pre-scan: does this file contain any genuine '<District>, <State> -
    Key Indicators' header? If yes, it's a normal multi-district state/UT
    and bare '<State> - Key Indicators' headers are the (skippable) state
    summary. If no such header exists anywhere, this is a single-district
    UT and the bare header IS the data."""
    for raw_line in lines:
        stripped = raw_line.strip()
        m = DISTRICT_HEADER_RE.match(stripped)
        if m and m.group('name').strip().lower() != state_name.lower():
            return True
    return False


def parse_state_file(path, state_name):
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]

    multi_district = _is_multi_district(lines, state_name)

    rows = []
    current_district = None
    current_category = None
    in_district_block = False
    pending = None  # {'num': str, 'text': str} awaiting a values-only line

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped == '\x0c':
            continue

        header_match = DISTRICT_HEADER_RE.match(stripped)
        if header_match:
            candidate = header_match.group('name').strip()
            pending = None
            if candidate.lower() == state_name.lower():
                in_district_block = False
                current_district = None
            else:
                current_district = candidate
                in_district_block = True
                current_category = None
            continue

        if not multi_district:
            bare_match = BARE_HEADER_RE.match(stripped)
            if bare_match and bare_match.group('name').strip().lower() == state_name.lower():
                # Single-district UT: this bare header IS the district table
                pending = None
                current_district = state_name
                in_district_block = True
                current_category = None
                continue

        if stripped.startswith('Appendix'):
            in_district_block = False
            current_district = None
            pending = None
            continue

        if not in_district_block or current_district is None:
            continue

        if pending is not None:
            # A pending wrapped entry is waiting on its value(s). Try to
            # resolve it FIRST, before considering this line a new indicator -
            # otherwise a values-only line like "4.7   6.5" gets misread as
            # "indicator 4, text '7'" (the decimal point collides with the
            # "NN." indicator-number pattern).
            m = VALUES_ONLY_RE.match(raw_line)
            if m:
                _emit(rows, state_name, current_district, current_category,
                      pending['num'], pending['text'], m.group('vals'))
                pending = None
                continue
            m = CONTINUATION_VALUES_RE.match(raw_line)
            if m:
                full_text = pending['text'] + ' ' + m.group('text').strip()
                _emit(rows, state_name, current_district, current_category,
                      pending['num'], full_text, m.group('vals'))
                pending = None
                continue
            # None of the value-completion patterns matched. If this line is
            # actually a complete new indicator (rare: a malformed prior wrap
            # left pending stuck), let it override rather than swallow it.
            m = INDICATOR_RE.match(raw_line)
            if m:
                pending = None
                _emit(rows, state_name, current_district, current_category,
                      m.group('num'), m.group('text'), m.group('vals'))
                continue
            # A category header appearing before values were found - abandon pending
            cat_m = CATEGORY_LINE_RE.match(stripped)
            if (cat_m and 'NFHS' not in stripped and not stripped.startswith('Indicators')):
                current_category = cat_m.group('name').strip()
                pending = None
                continue
            # Otherwise treat as continuation text for the pending entry's name
            pending['text'] += ' ' + stripped
            continue

        # No pending entry: check for a complete indicator line first
        m = INDICATOR_RE.match(raw_line)
        if m:
            _emit(rows, state_name, current_district, current_category,
                  m.group('num'), m.group('text'), m.group('vals'))
            continue

        m = INDICATOR_START_RE.match(raw_line)
        if m:
            pending = {'num': m.group('num'), 'text': m.group('text').strip()}
            continue

        # Category header
        cat_m = CATEGORY_LINE_RE.match(stripped)
        if (cat_m and not stripped.startswith('Indicators') and 'NFHS' not in stripped):
            current_category = cat_m.group('name').strip()

    return rows


if __name__ == '__main__':
    # Windows terminals default Python's stdout to cp1252, which can't
    # encode characters like "≥" that appear in some indicator names
    # (e.g. "Systolic ≥140 mm of Hg"). Force UTF-8 regardless of platform.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    txt_path, state_name = sys.argv[1], sys.argv[2]
    rows = parse_state_file(txt_path, state_name)
    writer = csv.DictWriter(sys.stdout, fieldnames=[
        'state', 'district', 'category', 'indicator_no', 'indicator',
        'nfhs6_value', 'nfhs5_value', 'small_sample_flag', 'boundary_change_single_round'
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

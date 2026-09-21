"""
Standardize filenames in a folder of NFHS-6 district CSVs and build one
combined all-India file.

Instead of trusting the filename (which may be "gujarat_nfhs6_district.csv",
"kerala_output.csv", or anything else depending on how it was generated),
this reads the 'state' column that's already inside each CSV - which is
always correct, since it came from the PDF's own title page - and uses
THAT to rename the file consistently and build the combined dataset.

Usage:
    python consolidate_data.py <data_folder>

What it does:
    1. Finds every .csv in <data_folder> (skips any existing combined file)
    2. Reads the 'state' column from each to determine which state it is
    3. Renames the file to "<state>_nfhs6_district.csv" (lowercase,
       underscores) if it isn't already named that
    4. Writes all_india_nfhs6_district.csv combining every file's rows
    5. Warns if two files claim to be the same state (possible duplicate
       or leftover old-version file) rather than silently overwriting
"""
import csv
import glob
import os
import sys

FIELDNAMES = [
    'state', 'district', 'category', 'indicator_no', 'indicator',
    'nfhs6_value', 'nfhs5_value', 'small_sample_flag', 'boundary_change_single_round'
]


def standard_filename(state_name):
    return state_name.strip().lower().replace(' ', '_').replace('&', 'and') + '_nfhs6_district.csv'


def main():
    if len(sys.argv) < 2:
        print("Usage: python consolidate_data.py <data_folder>")
        sys.exit(1)

    data_folder = sys.argv[1]
    combined_path = os.path.join(data_folder, 'all_india_nfhs6_district.csv')

    csv_paths = [
        p for p in glob.glob(os.path.join(data_folder, '*.csv'))
        if os.path.basename(p) != 'all_india_nfhs6_district.csv'
        and os.path.basename(p) != 'all_states_nfhs6_district.csv'  # older combined-file name, if present
    ]

    if not csv_paths:
        print(f"No CSV files found in {data_folder}")
        sys.exit(1)

    seen_states = {}  # state_name -> file path, to catch duplicates
    all_rows = []
    rename_log = []
    problems = []

    for path in csv_paths:
        try:
            with open(path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            problems.append((os.path.basename(path), f"could not read file: {e}"))
            continue

        if not rows:
            problems.append((os.path.basename(path), "file has no data rows"))
            continue

        states_in_file = set(r.get('state', '').strip() for r in rows)
        if len(states_in_file) != 1:
            problems.append((
                os.path.basename(path),
                f"expected exactly one state per file, found {len(states_in_file)}: {states_in_file}"
            ))
            continue

        state_name = states_in_file.pop()
        if not state_name:
            problems.append((os.path.basename(path), "state column is blank"))
            continue

        if state_name in seen_states:
            problems.append((
                os.path.basename(path),
                f"DUPLICATE - '{state_name}' already found in {os.path.basename(seen_states[state_name])}. "
                f"Skipped to avoid double-counting - check if one of these is an old/stale file."
            ))
            continue
        seen_states[state_name] = path

        target_name = standard_filename(state_name)
        target_path = os.path.join(data_folder, target_name)
        if os.path.basename(path) != target_name:
            if os.path.exists(target_path) and target_path != path:
                problems.append((os.path.basename(path),
                                  f"wanted to rename to {target_name} but that file already exists - skipped rename"))
            else:
                os.rename(path, target_path)
                rename_log.append((os.path.basename(path), target_name))
                path = target_path

        all_rows.extend(rows)

    if all_rows:
        with open(combined_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for r in all_rows:
                writer.writerow(r)

    print(f"\nStates combined: {len(seen_states)}")
    print(f"Total rows in combined file: {len(all_rows)}")
    print(f"Combined file: {combined_path}\n")

    if rename_log:
        print("Renamed:")
        for old, new in rename_log:
            print(f"  {old}  ->  {new}")
        print()

    if problems:
        print("Needs your attention:")
        for fname, msg in problems:
            print(f"  {fname}: {msg}")


if __name__ == '__main__':
    main()

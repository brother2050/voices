import csv
import re
from pathlib import Path

SOURCE_MD = Path('content.md')
TARGET_CSV = Path('voices.csv')

FIELD_KEYS = [
    ('- **角色身份**', 'role'),
    ('- **适配场景**', 'scene'),
    ('- **年龄**', 'age'),
    ('- **性别**', 'gender'),
    ('- **口音语言**', 'accent'),
    ('- **语气情绪**', 'mood'),
    ('- **语速音量**', 'speed'),
]
CSV_HEADER = [
    'id',
    'video_name',
    'title',
    'role',
    'scene',
    'age',
    'gender',
    'accent',
    'mood',
    'speed',
    'sample_text',
]


def normalize_sample_text(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n')]
    return '\\n'.join(lines).strip()


def parse_entry(entry_text: str) -> dict:
    lines = entry_text.splitlines()
    fields = {'role': '', 'scene': '', 'age': '', 'gender': '', 'accent': '', 'mood': '', 'speed': '', 'sample_text': ''}
    sample_lines = []
    sample_mode = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- **示例文案**'):
            sample_mode = True
            if ':' in stripped:
                rest = stripped.split('：', 1)[1].strip()
                if rest:
                    sample_lines.append(rest)
            continue

        if sample_mode:
            if stripped.startswith('- **'):
                sample_mode = False
            else:
                sample_lines.append(stripped)
                continue

        for prefix, key in FIELD_KEYS:
            if stripped.startswith(prefix):
                parts = stripped.split('：', 1)
                fields[key] = parts[1].strip() if len(parts) > 1 else ''
                break

    if sample_lines:
        sample_text = '\n'.join(line.lstrip('> ').rstrip() for line in sample_lines if line)
        fields['sample_text'] = normalize_sample_text(sample_text)
    return fields


def parse_markdown(md_text: str) -> list[dict]:
    pattern = re.compile(r'###\s*(\d+)\.\s*([^\n]+)\n(.*?)(?=###\s*\d+\. |\Z)', re.S)
    entries = []
    for match in pattern.finditer(md_text):
        id_ = match.group(1).strip()
        title = match.group(2).strip()
        body = match.group(3).strip()
        fields = parse_entry(body)
        fields.update({'id': id_, 'title': title})
        entries.append(fields)
    return entries


def read_csv_rows(csv_path: Path) -> list[list[str]]:
    if not csv_path.exists():
        return []
    with csv_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        return [row for row in reader]


def write_csv_rows(csv_path: Path, rows: list[list[str]]) -> None:
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in rows:
            if row and len(row) >= 11:
                row = row[:10] + [normalize_sample_text(row[10])]
            writer.writerow(row)


def ensure_header_exists(csv_path: Path) -> None:
    if not csv_path.exists():
        write_csv_rows(csv_path, [CSV_HEADER])


def append_entries(entries: list[dict]) -> int:
    with TARGET_CSV.open('a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for entry in entries:
            row = [
                entry['id'],
                f"{entry['id']}_{entry['title']}",
                entry['title'],
                entry['role'],
                entry['scene'],
                entry['age'],
                entry['gender'],
                entry['accent'],
                entry['mood'],
                entry['speed'],
                normalize_sample_text(entry['sample_text']),
            ]
            writer.writerow(row)
    return len(entries)


def replace_existing_rows(existing_rows: list[list[str]], entries: list[dict]) -> list[list[str]]:
    header = existing_rows[:1] if existing_rows else [CSV_HEADER]
    existing_body = existing_rows[1:] if len(existing_rows) > 1 else []
    parsed_ids = {entry['id'] for entry in entries}
    filtered_body = [row for row in existing_body if row and row[0] not in parsed_ids]
    new_rows = [
        [
            entry['id'],
            f"{entry['id']}_{entry['title']}",
            entry['title'],
            entry['role'],
            entry['scene'],
            entry['age'],
            entry['gender'],
            entry['accent'],
            entry['mood'],
            entry['speed'],
            normalize_sample_text(entry['sample_text']),
        ]
        for entry in entries
    ]
    return header + filtered_body + new_rows


def main() -> None:
    markdown = SOURCE_MD.read_text(encoding='utf-8')
    entries = parse_markdown(markdown)
    if not entries:
        raise SystemExit('No entries parsed from content.md')
    existing_rows = read_csv_rows(TARGET_CSV)
    if not existing_rows:
        write_csv_rows(TARGET_CSV, [CSV_HEADER])
        existing_rows = [CSV_HEADER]

    existing_ids = {row[0] for row in existing_rows[1:] if row}
    parsed_ids = {entry['id'] for entry in entries}
    overlap = existing_ids & parsed_ids

    if overlap:
        updated_rows = replace_existing_rows(existing_rows, entries)
        write_csv_rows(TARGET_CSV, updated_rows)
        print(f'Replaced {len(overlap)} existing rows and wrote {len(updated_rows)-1} total data rows to {TARGET_CSV.name}')
    else:
        count = append_entries(entries)
        print(f'Appended {count} rows to {TARGET_CSV.name}')


if __name__ == '__main__':
    main()

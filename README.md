# Smoking cessation newsletter renderer

Renders a weekly newsletter template once per recipient, mail-merge style, and writes each result to a text file. Python 3 standard library only.

## Usage

```
./send.py --recipient-list <csv_file> --payload-template <text_file> --output-dir <output_subdir>
```

- `--recipient-list`: a CSV file with no header row and two columns, full name and email address. Quote names that contain commas (`"Smith, John",john@example.com`). Blank lines are skipped and surrounding whitespace is trimmed.
- `--payload-template`: a UTF-8 text email payload. `{FULL_NAME}` (or `{ FULL_NAME }`) is replaced with each recipient's name. Any other `{IDENTIFIER}` is rejected as unsupported. Braces around anything else, such as `{}` or `{1 + 2}`, are left as they are.
- `--output-dir`: where rendered payloads are written, one file per recipient named `<email>.txt` (lowercased). The directory is created if it doesn't exist. Existing files with the same name are overwritten.

All input is validated before anything is written. Invalid input, such as a wrong column count, an empty name, a malformed or duplicate email address, or an unsupported template variable, exits with status 1 and an error naming the file and line.

Try it on the bundled samples:

```
./send.py --recipient-list examples/recipients.csv --payload-template examples/newsletter.txt --output-dir out
```

## Tests

```
python3 -m unittest discover -s tests
```

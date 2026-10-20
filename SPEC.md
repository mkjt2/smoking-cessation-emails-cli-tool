# Smoking cessation email list CLI tool

## The brief

We will help people with smoking cessation by sending out weekly newsletters with tips and encouragement.

The operator of the CLI tool will provide three pieces of information:

- Recipient list info.
- Newsletter payload.

The CLI tools job is to render the newsletters mail-merge style and output them as text files in local subfolder.

## Details

```
./send.py --recipient-list <csv_file> --payload-template <text_file> --output-dir <output_subdir>

```
* --recipient-list: the CSV file should have no headers, two columns: full name, and email address.
* --payload-template: it should be a text format email payload, with support for `{ }` style template variables.  Only `FULL_NAME` variable will be supported.
* --output-dir: where rendered payloads should go.  File names are based on recipient email addresses.  If the output dir does not yet exist, it will be created by the CLI tool.


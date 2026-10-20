import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import send  # noqa: E402


class SendTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, content):
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return path

    def main(self, csv_text, template_text, out_name="out"):
        csv_path = self.write("recipients.csv", csv_text)
        tpl_path = self.write("template.txt", template_text)
        out = self.tmp / out_name
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = send.main([
                "--recipient-list", str(csv_path),
                "--payload-template", str(tpl_path),
                "--output-dir", str(out),
            ])
        return code, out, stdout.getvalue(), stderr.getvalue()


class TestRendering(SendTestCase):
    def test_renders_one_file_per_recipient(self):
        code, out, stdout, _ = self.main(
            "Jane Doe,jane@example.com\nJohn Smith,john@example.com\n",
            "Hi {FULL_NAME},\nStay strong!\n",
        )
        self.assertEqual(code, 0)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["jane@example.com.txt", "john@example.com.txt"])
        self.assertEqual((out / "jane@example.com.txt").read_text(), "Hi Jane Doe,\nStay strong!\n")
        self.assertEqual((out / "john@example.com.txt").read_text(), "Hi John Smith,\nStay strong!\n")
        self.assertIn("Rendered 2 newsletter(s)", stdout)

    def test_creates_nested_output_dir(self):
        code, out, _, _ = self.main("A,a@example.com\n", "{FULL_NAME}", out_name="a/b/c")
        self.assertEqual(code, 0)
        self.assertTrue((out / "a@example.com.txt").is_file())

    def test_existing_output_dir_is_reused(self):
        (self.tmp / "out").mkdir()
        code, out, _, _ = self.main("A,a@example.com\n", "{FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertEqual((out / "a@example.com.txt").read_text(), "A")

    def test_spaced_placeholder_and_multiple_occurrences(self):
        code, out, _, _ = self.main("Ann,ann@example.com\n", "{ FULL_NAME } / {FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertEqual((out / "ann@example.com.txt").read_text(), "Ann / Ann")

    def test_non_variable_braces_are_left_alone(self):
        code, out, _, _ = self.main("Ann,ann@example.com\n", "{} {1 + 2} {FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertEqual((out / "ann@example.com.txt").read_text(), "{} {1 + 2} Ann")

    def test_name_containing_braces_is_inserted_literally(self):
        code, out, _, _ = self.main('"{FULL_NAME} \\1",x@example.com\n', "Hi {FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertEqual((out / "x@example.com.txt").read_text(), "Hi {FULL_NAME} \\1")

    def test_quoted_name_with_comma_and_unicode(self):
        code, out, _, _ = self.main('"Smith, Zoë",zoe@example.com\n', "Hi {FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertEqual((out / "zoe@example.com.txt").read_text(encoding="utf-8"), "Hi Smith, Zoë")

    def test_whitespace_trimmed_and_blank_lines_skipped(self):
        code, out, _, _ = self.main("\n  Ann Lee ,  ann@example.com  \n\n", "[{FULL_NAME}]")
        self.assertEqual(code, 0)
        self.assertEqual((out / "ann@example.com.txt").read_text(), "[Ann Lee]")

    def test_utf8_bom_is_ignored(self):
        code, out, _, _ = self.main("\ufeffAnn,ann@example.com\n", "{FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertEqual((out / "ann@example.com.txt").read_text(), "Ann")

    def test_file_name_is_lowercased_email(self):
        code, out, _, _ = self.main("Ann,Ann@Example.COM\n", "{FULL_NAME}")
        self.assertEqual(code, 0)
        self.assertTrue((out / "ann@example.com.txt").is_file())


class TestErrors(SendTestCase):
    def assertFails(self, csv_text, template_text, message):
        code, out, _, stderr = self.main(csv_text, template_text)
        self.assertEqual(code, 1)
        self.assertIn(message, stderr)
        self.assertFalse(out.exists(), "nothing should be written when validation fails")

    def test_wrong_column_count(self):
        self.assertFails("Ann,ann@example.com,extra\n", "{FULL_NAME}", "expected 2 columns")
        self.assertFails("Ann\n", "{FULL_NAME}", "expected 2 columns")

    def test_empty_name(self):
        self.assertFails(" ,ann@example.com\n", "{FULL_NAME}", "full name is empty")

    def test_invalid_emails(self):
        for bad in ["", "no-at-sign", "a@b@c", "has space@x.com", "../evil@x", "a/b@x.com"]:
            with self.subTest(email=bad):
                self.assertFails(f"Ann,{bad}\n", "{FULL_NAME}", "invalid email address")

    def test_duplicate_email_case_insensitive(self):
        self.assertFails(
            "Ann,ann@example.com\nAnn Two,ANN@example.com\n", "{FULL_NAME}",
            "duplicate email address 'ANN@example.com' (first seen on line 1)",
        )

    def test_error_reports_line_number(self):
        self.assertFails("Ann,ann@example.com\nBob,bad\n", "{FULL_NAME}", "recipients.csv:2:")

    def test_empty_recipient_list(self):
        self.assertFails("\n\n", "{FULL_NAME}", "has no recipients")

    def test_unsupported_template_variable(self):
        self.assertFails("Ann,ann@example.com\n", "{FULL_NAME} {EMAIL} {first}", "unsupported variable(s): EMAIL, first")

    def test_missing_recipient_list(self):
        tpl = self.write("t.txt", "x")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = send.main(["--recipient-list", str(self.tmp / "nope.csv"),
                              "--payload-template", str(tpl), "--output-dir", str(self.tmp / "out")])
        self.assertEqual(code, 1)
        self.assertIn("cannot read recipient list", err.getvalue())

    def test_missing_template(self):
        csv_path = self.write("r.csv", "Ann,ann@example.com\n")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = send.main(["--recipient-list", str(csv_path),
                              "--payload-template", str(self.tmp / "nope.txt"), "--output-dir", str(self.tmp / "out")])
        self.assertEqual(code, 1)
        self.assertIn("cannot read payload template", err.getvalue())

    def test_output_dir_is_a_file(self):
        self.write("out", "")
        code, _, _, stderr = self.main("Ann,ann@example.com\n", "{FULL_NAME}")
        self.assertEqual(code, 1)
        self.assertIn("cannot create output directory", stderr)

    def test_missing_required_argument(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            send.main(["--recipient-list", "x.csv"])
        self.assertEqual(cm.exception.code, 2)


class TestCommandLine(SendTestCase):
    def test_executable_end_to_end_with_examples(self):
        out = self.tmp / "rendered"
        result = subprocess.run(
            [str(ROOT / "send.py"),
             "--recipient-list", str(ROOT / "examples/recipients.csv"),
             "--payload-template", str(ROOT / "examples/newsletter.txt"),
             "--output-dir", str(out)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            sorted(p.name for p in out.iterdir()),
            ["jane.doe@example.com.txt", "john.smith@example.com.txt", "zoe@example.org.txt"],
        )
        body = (out / "john.smith@example.com.txt").read_text(encoding="utf-8")
        self.assertIn("Hi Smith, John,", body)
        self.assertNotIn("{FULL_NAME}", body)


if __name__ == "__main__":
    unittest.main()

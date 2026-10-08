"""One-off wording fix: '1 variant spellings' becomes '1 variant spelling'. Run once from the project folder."""
import pathlib

path = pathlib.Path("engines/quality/engine.py")
text = path.read_text(encoding="utf-8")

old = '''f"Merged {len(mapping)} variant spellings into their standard value.",'''
new = '''f"Merged {len(mapping)} variant {'spelling' if len(mapping) == 1 else 'spellings'} into their standard value.",'''

if new in text:
    print("Already applied. Nothing to do.")
else:
    assert old in text, "The expected line was not found. Send the file to your mentor."
    path.write_text(text.replace(old, new), encoding="utf-8")
    print("Wording fixed.")
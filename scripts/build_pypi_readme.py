#!/usr/bin/env python3
# Rewrite relative doc/ links in README.md to absolute GitHub URLs, so images
# and links render correctly on the PyPI package page (PyPI has no access to
# files outside the built distribution). Writes README_pypi.md at repo root,
# which pyproject.toml's readme= key points at. Regenerate before every build.

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_BASE = "https://raw.githubusercontent.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/main/"

def rewrite_relative_links(text):
    def replace(match):
        prefix, path = match.group(1), match.group(2)
        return f"{prefix}({RAW_BASE}{path})"

    return re.sub(r'(!?\[[^\]]*\])\(\./([^)]+)\)', replace, text)

def main():
    src_path = os.path.join(REPO_ROOT, 'README.md')
    dst_path = os.path.join(REPO_ROOT, 'README_pypi.md')

    with open(src_path, 'r', encoding='utf-8') as f:
        text = f.read()

    text = rewrite_relative_links(text)

    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'Wrote {dst_path}')

if __name__ == '__main__':
    main()

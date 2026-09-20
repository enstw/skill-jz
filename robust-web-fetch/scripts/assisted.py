# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.40", "pypdf>=4", "markdownify"]
# ///
"""Compatibility entry point; authenticated-fetch owns the workflow."""
import runpy
import sys
from fetch_common import resolve_skill

if __name__ == '__main__':
    try:
        skill = resolve_skill('authenticated-fetch', __file__)
    except RuntimeError as error:
        raise SystemExit(str(error))
    print('assisted.py moved to authenticated-fetch; forwarding this command.', file=sys.stderr)
    runpy.run_path(str(skill / 'scripts/assisted.py'), run_name='__main__')

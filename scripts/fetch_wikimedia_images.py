#!/usr/bin/env python3
"""Robust Wikimedia image fetcher for SkyTrain stations.

Features:
- Searches English Wikipedia for each station page
- Tries `pageimages` original image, then falls back to `images` + `imageinfo`
- Writes mapping to a Python file and can optionally replace the `stationImages` dict in `utils.py` (backup created)

Usage:
  python scripts/fetch_wikimedia_images.py [--write] [--yes] [--out FILE]
"""

import argparse
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UTILS_PATH = ROOT / 'utils.py'
DEFAULT_OUT = ROOT / 'wikimedia_images.py'
WIKI_API = 'https://en.wikipedia.org/w/api.php'
HEADERS = {'User-Agent': 'CompassWrappedImageFetcher/1.0 (you@example.com)'}


def find_page_title(query):
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'format': 'json',
        'srlimit': 1
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    hits = data.get('query', {}).get('search', [])
    return hits[0]['title'] if hits else None


def _is_bad_image_url(url: str) -> bool:
    """Detect common non-photographic / placeholder / disambiguation images."""
    if not url:
        return True
    u = url.lower()
    bad_keywords = (
        'disambig', 'disambiguation', 'placeholder', 'noimage', 'commons-logo',
        'wikimedia-logo', 'logo', 'symbol', 'button', 'map', 'diagram', 'locmap', 'locator'
    )
    for k in bad_keywords:
        if k in u:
            return True
    # tiny SVG icons used by templates are also not useful; check for small-width thumbnails ("thumb")
    if '/thumb/' in u and u.endswith('.svg') and 'disambig' in u:
        return True
    return False


def _is_preferred_ext(url: str) -> bool:
    ext = url.rsplit('.', 1)[-1].lower() if '.' in url else ''
    return ext in ('jpg', 'jpeg', 'png')


def get_image_for_title(title):
    # Try pageimages original first, but validate for placeholders/disambigs
    params = {
        'action': 'query',
        'prop': 'pageimages',
        'piprop': 'original',
        'titles': title,
        'format': 'json'
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    pages = data.get('query', {}).get('pages', {}).values()

    for p in pages:
        img = p.get('original', {}).get('source')
        if img and 'upload.wikimedia.org' in img and not _is_bad_image_url(img):
            # prefer jpg/png; if svg, only accept if no better option found later
            if _is_preferred_ext(img):
                return img
            # keep as fallback candidate but keep searching for better ones
            fallback_svg = img
            break
    else:
        fallback_svg = None

    # Fallback: list page images then query imageinfo for suitable files
    params2 = {'action': 'query', 'prop': 'images', 'titles': title, 'format': 'json'}
    r2 = requests.get(WIKI_API, params=params2, headers=HEADERS, timeout=15)
    r2.raise_for_status()
    data2 = r2.json()
    pages2 = data2.get('query', {}).get('pages', {}).values()
    image_titles = []
    for p in pages2:
        for img in p.get('images', []) if p.get('images') else []:
            t = img.get('title')
            if t:
                image_titles.append(t)

    # Prefer raster images first (jpg/png), then consider svg only if necessary
    preferred = [t for t in image_titles if t.lower().endswith(('.jpg', '.jpeg', '.png'))]
    fallback_svgs = [t for t in image_titles if t.lower().endswith('.svg')]

    for it in preferred + fallback_svgs:
        # skip clearly bad image titles
        it_low = it.lower()
        if any(k in it_low for k in ('disambig', 'disambiguation', 'placeholder', 'logo', 'commons-logo')):
            continue
        params3 = {'action': 'query', 'titles': it, 'prop': 'imageinfo', 'iiprop': 'url', 'format': 'json'}
        r3 = requests.get(WIKI_API, params=params3, headers=HEADERS, timeout=15)
        r3.raise_for_status()
        data3 = r3.json()
        for p in data3.get('query', {}).get('pages', {}).values():
            ii = p.get('imageinfo', [])
            if ii:
                url = ii[0].get('url')
                if url and 'upload.wikimedia.org' in url and not _is_bad_image_url(url):
                    # If raster -> accept; if svg, accept only if no raster candidate found yet
                    if _is_preferred_ext(url):
                        return url
                    svg_candidate = url
    # If we found an SVG fallback from pageimages original or imageinfo, return it as last resort
    if 'svg_candidate' in locals():
        return svg_candidate
    if fallback_svg:
        return fallback_svg

    return None


def load_stations():
    # Import utils.py dynamically to get authoritative station list
    import importlib.util
    spec = importlib.util.spec_from_file_location('cwutils', str(UTILS_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, 'SkyTrainStns')


def generate_mapping(stations):
    results = {}
    missing = []

    for i, st in enumerate(stations, start=1):
        print(f'{i}/{len(stations)}: {st}')
        query = st.replace(' Stn', '').replace('\u2013', '-').replace('–', '-')
        title = None
        try:
            title = find_page_title(query + ' station') or find_page_title(query)
        except Exception as e:
            print('  Search error:', e)

        img = None
        if title:
            try:
                img = get_image_for_title(title)
            except Exception as e:
                print('  Image fetch error:', e)

        if not img:
            try:
                alt_title = find_page_title(st)
                if alt_title and alt_title != title:
                    img = get_image_for_title(alt_title)
            except Exception:
                pass

        if not img:
            try:
                short = query.split(' - ')[0]
                t3 = find_page_title(short)
                if t3:
                    img = get_image_for_title(t3)
            except Exception:
                pass

        if img:
            results[st] = img
            print('  Found ->', img)
        else:
            missing.append(st)
            print('  Missing image')

        time.sleep(0.6)

    return results, missing


def write_output(mapping, out_path: Path):
    s = '# Generated mapping of station -> image (run scripts/fetch_wikimedia_images.py to regenerate)\n'
    s += 'stationImages = {\n'
    for k, v in sorted(mapping.items()):
        s += f'    "{k}": "{v}",\n'
    s += '}\n'
    out_path.write_text(s, encoding='utf-8')
    print('Wrote mapping to', out_path)


def replace_station_images_in_utils(mapping, dry_run=True):
    text = UTILS_PATH.read_text(encoding='utf-8')
    pattern = re.compile(r"stationImages\s*=\s*\{.*?\}\n", re.S)
    new_block = '# --- Station images (generated) ---\nstationImages = {\n'
    for k, v in sorted(mapping.items()):
        new_block += f'    "{k}": "{v}",\n'
    new_block += '}\n'

    if not pattern.search(text):
        raise RuntimeError('Could not find existing stationImages block in utils.py')

    new_text = pattern.sub(new_block, text)

    if dry_run:
        print('DRY RUN: utils.py not modified. Pass --write to update file.')
        return

    backup = UTILS_PATH.with_suffix('.py.bak')
    backup.write_text(text, encoding='utf-8')
    UTILS_PATH.write_text(new_text, encoding='utf-8')
    print('Updated utils.py and wrote backup to', backup)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Write updates into utils.py')
    parser.add_argument('--yes', action='store_true', help='Auto-confirm write')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT, help='Write mapping to FILE')
    args = parser.parse_args()

    stations = load_stations()
    mapping, missing = generate_mapping(stations)

    print('\nSummary:')
    print(f'Found {len(mapping)} images; {len(missing)} missing')
    if missing:
        print('Missing stations:')
        for m in missing:
            print('  ', m)

    write_output(mapping, args.out)

    if args.write:
        if not args.yes:
            r = input('This will replace the `stationImages` dict in utils.py (backup will be created). Proceed? [y/N] ')
            if r.lower() != 'y':
                print('Aborting.')
                return
        replace_station_images_in_utils(mapping, dry_run=not args.write)


if __name__ == '__main__':
    main()

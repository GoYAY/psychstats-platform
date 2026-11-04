"""Synchronize selected draft metadata without touching public review status."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'site/content'
META = ('id', 'zh', 'en', 'aliases', 'type', 'level', 'topic', 'status', 'summary', 'relations')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ids', nargs='+')
    args = parser.parse_args()
    registry = json.loads((ROOT / 'registry.json').read_text(encoding='utf-8'))
    curriculum = json.loads((ROOT / 'curriculum.json').read_text(encoding='utf-8'))
    lookup = {term['id']: term for term in registry['terms']}
    for slug in args.ids:
        term = json.loads((ROOT / 'drafts' / f'{slug}.json').read_text(encoding='utf-8'))
        if slug in lookup:
            old = lookup[slug]
            old.update({key: term[key] for key in META if key != 'status'})
        else:
            registry['terms'].append({key: term[key] for key in META})
        destination = next(topic for topic in curriculum['topics'] if topic['id'] == term['topic'])
        for topic in curriculum['topics']:
            if topic is not destination and slug in topic['terms']:
                topic['terms'].remove(slug)
        if slug not in destination['terms']:
            prerequisites = term['relations'].get('prerequisites', [])
            positions = [destination['terms'].index(p) for p in prerequisites if p in destination['terms']]
            destination['terms'].insert(max(positions, default=-1) + 1, slug)
    for filename, content in [('registry.json', registry), ('curriculum.json', curriculum)]:
        (ROOT / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Generate conf.bib from conf/*.yaml files."""

import os
import glob
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
CONF_DIR = os.path.join(ROOT_DIR, 'conf')
OUTPUT = os.path.join(ROOT_DIR, 'conf.bib')

POT_STRING = 'Proceedings of the '
DEFAULT_TITLE = 'POT # {{ {edition} }} # {conf}'

# BibTeX month macros — these are output without braces/quotes
BIBTEX_MONTHS = {'jan', 'feb', 'mar', 'apr', 'may', 'jun',
                 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'}


def load_conferences():
    """Load all conf/*.yaml files, return sorted list of (conf_name, data)."""
    confs = []
    for path in sorted(glob.glob(os.path.join(CONF_DIR, '*.yaml'))):
        filename = os.path.basename(path)
        conf_name = os.path.splitext(filename)[0].upper()
        with open(path) as f:
            data = yaml.safe_load(f)
        confs.append((conf_name, data))
    return confs


def make_key(conf_name, entry, key_digits=2):
    """Generate proceedings key like SOSP19 or OLS2002."""
    year = entry['year']
    if key_digits == 4:
        year_part = str(year)
    else:
        year_part = f'{year % 100:02d}'
    suffix = entry.get('key_suffix', '')
    return f'{conf_name}{year_part}{suffix}'


def render_title(template, conf_name, entry):
    """Render a title template with entry data."""
    return template.format(
        conf=conf_name,
        edition=entry.get('edition', ''),
        suffix=entry.get('suffix', ''),
        esec_edition=entry.get('esec_edition', ''),
    )


def format_field(name, value, is_numeric=False, is_macro=False):
    """Format a single BibTeX field line."""
    if is_macro:
        return f'  {name:<13}= {value},'
    elif is_numeric:
        return f'  {name:<13}= {value},'
    else:
        return f'  {name:<13}= {{{value}}},'


def is_month_macro(value):
    """Check if a month value is a bare BibTeX macro (not braced)."""
    # Simple month: "oct", or compound: "may # {--} # jun"
    parts = value.split('#')
    return all(p.strip().strip('{}').strip('"').strip() in BIBTEX_MONTHS
               or p.strip().startswith('{') or p.strip().startswith('"')
               for p in parts)


def generate_entry(conf_name, string_key, entry, title_template, key_digits):
    """Generate a single @Proceedings block."""
    key = make_key(conf_name, entry, key_digits)

    # Use per-entry title override if present, otherwise conference template
    template = entry.get('title', title_template)
    title = render_title(template, string_key, entry)

    lines = [f'@Proceedings{{{key},']
    lines.append(format_field('title', title, is_macro=True))
    lines.append(format_field('booktitle', title, is_macro=True))

    # Journal (for journal-style entries)
    if 'journal' in entry:
        lines.append(format_field('journal', entry['journal']))

    # Year (numeric, no braces)
    lines.append(format_field('year', entry['year'], is_numeric=True))

    # Month (macro, no braces)
    if 'month' in entry:
        lines.append(format_field('month', entry['month'], is_macro=True))

    # Volume and number
    if 'volume' in entry:
        lines.append(format_field('volume', entry['volume']))
    if 'number' in entry:
        lines.append(format_field('number', entry['number']))

    # Address
    if 'address' in entry:
        lines.append(format_field('address', entry['address']))

    lines.append('}')
    return lines


def generate_bib(conferences):
    """Generate the full conf.bib content."""
    lines = []

    # POT string
    lines.append(f'@string{{POT       = {{{POT_STRING}}}}}')
    lines.append('')

    # String macros for each conference
    for conf_name, data in conferences:
        name = data.get('name', '')
        if name:
            string_key = data.get('string_key', conf_name)
            padded = string_key.ljust(10)
            lines.append(f'@string{{{padded}= {{{name}}}}}')
    lines.append('')

    # Proceedings entries
    for conf_name, data in conferences:
        string_key = data.get('string_key', conf_name)
        title_template = data.get('title', DEFAULT_TITLE)
        key_digits = data.get('key_digits', 2)
        entries = data.get('entries', [])

        if not entries:
            continue

        lines.append('%% ' + '-' * 70)
        lines.append(f'%% {conf_name}')
        lines.append('%% ' + '-' * 70)

        for entry in entries:
            lines.extend(generate_entry(conf_name, string_key, entry, title_template, key_digits))
            lines.append('')

    return '\n'.join(lines) + '\n'


def main():
    conferences = load_conferences()
    content = generate_bib(conferences)
    with open(OUTPUT, 'w') as f:
        f.write(content)
    print(f'Generated {OUTPUT} ({content.count(chr(10))} lines)')


if __name__ == '__main__':
    main()

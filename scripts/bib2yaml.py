#!/usr/bin/env python3
"""One-time converter: parse conf.bib and generate conf/*.yaml files."""

import os
import re
import yaml

BIB_PATH = os.path.join(os.path.dirname(__file__), '..', 'conf.bib')
CONF_DIR = os.path.join(os.path.dirname(__file__), '..', 'conf')

# Default title template (when omitted from YAML)
DEFAULT_TEMPLATE = 'POT # {{ {edition} }} # {conf}'


def parse_bib(path):
    """Parse conf.bib into string definitions and proceedings entries."""
    with open(path) as f:
        content = f.read()

    # Parse @string definitions
    strings = {}
    for m in re.finditer(r'@string\{(\w+)\s*=\s*\{([^}]*)\}\}', content, re.IGNORECASE):
        key, value = m.group(1), m.group(2)
        if key != 'POT':
            strings[key] = value

    # Parse @Proceedings entries
    entries = []
    # Match @Proceedings{KEY, ... } blocks
    pattern = re.compile(
        r'@Proceedings\{(\w+),\s*(.*?)\n\}',
        re.DOTALL | re.IGNORECASE
    )
    for m in pattern.finditer(content):
        key = m.group(1)
        body = m.group(2)
        fields = parse_fields(body)
        fields['_key'] = key
        entries.append(fields)

    return strings, entries


def parse_fields(body):
    """Parse BibTeX fields from an entry body."""
    fields = {}
    # Match field = value patterns
    # Value can be: {text}, "text", number, or macro # concatenation
    for m in re.finditer(
        r'(\w+)\s*=\s*(.*?)(?:,\s*$|\s*$)',
        body, re.MULTILINE
    ):
        fname = m.group(1).strip().lower()
        fval = m.group(2).strip().rstrip(',').strip()
        fields[fname] = fval
    return fields


def analyze_title(title_expr, conf_key):
    """Analyze a title expression and return (template, edition, suffix) or None.

    Returns:
        (template_str_or_None, edition_str_or_None, suffix_str_or_None)
        template_str is None if it matches the default template.
    """
    title = title_expr.strip()

    # Pattern: bare CONF (e.g., "BLACKHAT")
    if re.match(r'^[A-Z]+$', title):
        return ('{conf}', None, None)

    # Pattern: POT # CONF (no edition, e.g., "POT # OLS")
    m = re.match(r'^POT\s*#\s*([A-Z]+)\s*$', title)
    if m:
        return ('POT # {conf}', None, None)

    # Pattern: POT # "text" # CONF or POT # {text} # CONF
    m = re.match(r'^POT\s*#\s*["{]\s*(.*?)\s*["}]\s*#\s*([A-Z]+)\s*$', title)
    if m:
        edition = m.group(1)
        # This matches the default template
        return (None, edition, None)

    # Pattern: {text} # CONF # {suffix}
    m = re.match(r'^\{\s*(.*?)\s*\}\s*#\s*([A-Z]+)\s*#\s*\{\s*(.*?)\s*\}\s*$', title)
    if m:
        edition = m.group(1)
        suffix = m.group(3)
        template = '{{ {edition} }} # {conf} # {{ {suffix} }}'
        return (template, edition, suffix)

    # Pattern: {text} # CONF (no POT)
    m = re.match(r'^\{\s*(.*?)\s*\}\s*#\s*([A-Z]+)\s*$', title)
    if m:
        edition = m.group(1)
        template = '{{ {edition} }} # {conf}'
        return (template, edition, None)

    # Fallback: store as title_override
    return (title, None, None)


def extract_conf_from_key(key):
    """Extract conference name from a proceedings key like SOSP19 or ATC85S."""
    # Special case: BLACKHATASIA19
    if key.startswith('BLACKHATASIA'):
        return 'BLACKHATASIA'
    # Special case: ESECFSE
    if key.startswith('ESECFSE'):
        return 'ESECFSE'
    # General: strip trailing digits and optional letter suffix
    m = re.match(r'^([A-Z]+?)(\d{2,4}[A-Z]?)$', key)
    if m:
        return m.group(1)
    return key


def extract_year_suffix(key, conf_name):
    """Extract year part and optional suffix from key."""
    remainder = key[len(conf_name):]
    # e.g., "85S" -> year_part="85", suffix="S"
    # e.g., "2002" -> year_part="2002", suffix=""
    # e.g., "19" -> year_part="19", suffix=""
    m = re.match(r'^(\d{2,4})([A-Z]?)$', remainder)
    if m:
        return m.group(1), m.group(2)
    return remainder, ''


def parse_month(month_str):
    """Parse a month field value, returning it as-is (it's a BibTeX macro)."""
    return month_str.strip()


def convert():
    strings, entries = parse_bib(BIB_PATH)

    # Group entries by conference
    conferences = {}
    for entry in entries:
        key = entry['_key']
        conf = extract_conf_from_key(key)
        if conf not in conferences:
            conferences[conf] = []
        conferences[conf].append(entry)

    os.makedirs(CONF_DIR, exist_ok=True)

    for conf_name, conf_entries in conferences.items():
        yaml_data = build_yaml(conf_name, conf_entries, strings)
        filename = conf_name.lower() + '.yaml'
        filepath = os.path.join(CONF_DIR, filename)
        with open(filepath, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, width=120)
        print(f'  Written: {filepath}')


def build_yaml(conf_name, conf_entries, strings):
    """Build YAML data structure for a conference."""
    # Get the @string name value
    name = strings.get(conf_name, '')

    # Analyze all entries to determine conference-level template
    templates = set()
    entry_data_list = []

    # Check if we need key_digits: 4
    has_4digit = any(len(extract_year_suffix(e['_key'], conf_name)[0]) == 4 for e in conf_entries)

    for entry in conf_entries:
        key = entry['_key']
        year_part, key_suffix = extract_year_suffix(key, conf_name)

        title_expr = entry.get('title', '')
        template, edition, suffix = analyze_title(title_expr, conf_name)
        templates.add(template)

        ed = {}
        if edition is not None and edition.strip():
            ed['edition'] = edition

        year_val = entry.get('year', '')
        if year_val:
            ed['year'] = int(year_val)

        month_val = entry.get('month', '')
        if month_val:
            ed['month'] = month_val

        address_val = entry.get('address', '')
        if address_val:
            # Strip braces
            address_val = address_val.strip('{}').strip()
            if address_val:
                ed['address'] = address_val

        if key_suffix:
            ed['key_suffix'] = key_suffix

        if suffix:
            ed['suffix'] = suffix

        # Handle journal-style entries
        for field in ('journal', 'volume', 'number'):
            val = entry.get(field, '')
            if val:
                ed[field] = val.strip('{}').strip()

        entry_data_list.append(ed)

    # Determine conference-level title template
    # Filter out None (default template)
    non_default = [t for t in templates if t is not None]

    yaml_data = {}
    yaml_data['name'] = name

    if len(non_default) == 1 and None not in templates:
        # All entries use the same non-default template
        yaml_data['title'] = non_default[0]
    elif len(non_default) > 0 and None in templates:
        # Mix of default and non-default - need per-entry title_override
        # For simplicity, if there's only one non-default, set it per-entry
        pass
    elif len(non_default) == 1 and None in templates:
        # Some default, some non-default
        pass
    elif len(non_default) > 1:
        # Multiple different non-default templates - per-entry title_override
        pass

    # If single non-default template covers all entries
    if non_default and len(non_default) == 1 and None not in templates:
        yaml_data['title'] = non_default[0]

    if has_4digit:
        yaml_data['key_digits'] = 4

    # Re-analyze to set per-entry title_override when needed
    for i, entry in enumerate(conf_entries):
        title_expr = entry.get('title', '')
        template, edition, suffix = analyze_title(title_expr, conf_name)

        # If template differs from conference-level template, store override
        conf_template = yaml_data.get('title')
        if template is not None and template != conf_template:
            entry_data_list[i]['title'] = template
            # If the template was the default and conf has a different template set
            if conf_template is not None:
                entry_data_list[i]['title'] = 'POT # {{ {edition} }} # {conf}'

    yaml_data['entries'] = entry_data_list
    return yaml_data


if __name__ == '__main__':
    convert()

"""
Parse a GenePattern module zip file and extract module info from the manifest.
"""

import zipfile
from typing import Any, Dict, List


def parse_properties(content: str) -> Dict[str, str]:
    """Parse a Java .properties format file (key=value pairs)."""
    props: Dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            props[key.strip()] = value
    return props


def unescape_value(value: str) -> str:
    """Unescape backslash-escaped characters in manifest values."""
    return value.replace('\\:', ':').replace('\\=', '=').replace('\\;', ';')


def parse_choices(choices_str: str) -> List[Dict[str, str]]:
    """Parse semicolon-separated choices: 'Label\\=value;Label2\\=value2'"""
    if not choices_str:
        return []
    result = []
    for choice in choices_str.split(';'):
        choice = choice.strip()
        if not choice:
            continue
        if '\\=' in choice:
            label, _, value = choice.partition('\\=')
            result.append({'label': label.strip(), 'value': value.strip()})
        else:
            result.append({'label': choice, 'value': choice})
    return result


def extract_module_info(zip_path: str) -> Dict[str, Any]:
    """
    Extract and parse module info from a GenePattern module zip file.

    Returns a dict with:
      name, description, docker_image, command_line, parameters,
      language, author, version, categories, task_type
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()

        # Find manifest — root level or one directory deep
        manifest_name = None
        for name in names:
            parts = [p for p in name.split('/') if p]
            if parts and parts[-1] == 'manifest' and len(parts) <= 2:
                manifest_name = name
                break

        if not manifest_name:
            raise ValueError(
                f"No 'manifest' file found in zip. Available files: {names[:30]}"
            )

        content = zf.read(manifest_name).decode('utf-8', errors='replace')

    props = parse_properties(content)

    # Docker image — unescape the colon
    docker_image = unescape_value(props.get('job.docker.image', '')) or None

    # Command line template
    command_line = props.get('commandLine', '')

    # Extract parameters sequentially (p1, p2, …)
    parameters: List[Dict[str, Any]] = []
    n = 1
    while f'p{n}_name' in props:
        prefix = f'p{n}_'

        param_type_raw = props.get(f'{prefix}TYPE', '')
        java_type = props.get(f'{prefix}type', '')

        if param_type_raw.upper() == 'FILE' or java_type == 'java.io.File':
            param_type = 'FILE'
        elif param_type_raw == 'Integer' or java_type == 'java.lang.Integer':
            param_type = 'INTEGER'
        elif param_type_raw in ('Float', 'Floating Point') or java_type == 'java.lang.Float':
            param_type = 'FLOAT'
        else:
            param_type = 'TEXT'

        choices_str = props.get(f'{prefix}value', '')

        parameters.append({
            'index': n,
            'name': props[f'{prefix}name'],
            'description': props.get(f'{prefix}description', ''),
            'type': param_type,
            'optional': props.get(f'{prefix}optional', '') == 'on',
            'default_value': props.get(f'{prefix}default_value', ''),
            'choices': parse_choices(choices_str),
            'num_values': props.get(f'{prefix}numValues', '1..1'),
            'prefix_when_specified': props.get(f'{prefix}prefix_when_specified', ''),
            'file_format': props.get(f'{prefix}fileFormat', ''),
            'mode': props.get(f'{prefix}MODE', ''),
        })
        n += 1

    return {
        'name': props.get('name', 'Unknown'),
        'description': props.get('description', ''),
        'docker_image': docker_image,
        'command_line': command_line,
        'parameters': parameters,
        'language': props.get('language', ''),
        'author': props.get('author', ''),
        'version': props.get('version', ''),
        'categories': props.get('categories', ''),
        'task_type': props.get('taskType', ''),
    }

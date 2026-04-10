"""
Run a GenePattern module in a local Docker container.
"""

import base64
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Module extraction ────────────────────────────────────────────────────────

def extract_module_to_dir(zip_path: str, target_dir: str) -> None:
    """
    Extract module zip into target_dir.

    If all files live under a single top-level directory inside the zip,
    that wrapper directory is stripped so target_dir contains the module
    files directly.
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()

        # Detect single top-level directory
        top_dirs = {n.split('/')[0] for n in names if '/' in n}
        top_files = [n for n in names if '/' not in n and not n.endswith('/')]
        strip_prefix: Optional[str] = None
        if len(top_dirs) == 1 and not top_files:
            strip_prefix = list(top_dirs)[0] + '/'

        for name in names:
            if name.endswith('/'):
                continue  # skip directory entries

            rel = name[len(strip_prefix):] if strip_prefix and name.startswith(strip_prefix) else name
            if not rel:
                continue

            target_path = Path(target_dir) / rel
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target_path, 'wb') as dst:
                dst.write(src.read())

    # Make scripts executable
    for pattern in ('*.sh', '*.py', '*.r', '*.R', '*.pl'):
        for f in Path(target_dir).rglob(pattern):
            f.chmod(f.stat().st_mode | 0o755)


# ─── Command line construction ────────────────────────────────────────────────

def build_command(
    command_line_template: str,
    parameters: List[Dict[str, Any]],
    param_values: Dict[str, str],
    libdir: str = '/module/',
) -> str:
    """
    Substitute parameter values into the commandLine template.

    Rules (mirrors GenePattern server behaviour):
    - <libdir>  → replaced with libdir (e.g. '/module/')
    - <param.name>  → if value provided: prefix_when_specified + value
                      if not provided (optional): empty string
    Trailing multi-spaces are collapsed.
    """
    cmd = command_line_template

    # Replace <libdir> first
    cmd = cmd.replace('<libdir>', libdir)

    param_map = {p['name']: p for p in parameters}

    # Iterate over all remaining placeholders in order
    for placeholder in re.findall(r'<([^>]+)>', cmd):
        if placeholder == 'libdir':
            continue

        param_info = param_map.get(placeholder, {})
        value = param_values.get(placeholder, '').strip()

        if not value:
            value = param_info.get('default_value', '').strip()

        if value:
            prefix = param_info.get('prefix_when_specified', '')
            replacement = f'{prefix}{value}'
        else:
            replacement = ''

        # Replace only the first occurrence (parameters are positional in template)
        cmd = cmd.replace(f'<{placeholder}>', replacement, 1)

    # Collapse runs of spaces
    cmd = re.sub(r' {2,}', ' ', cmd).strip()
    return cmd


# ─── Main runner ─────────────────────────────────────────────────────────────

def run_module(
    zip_path: str,
    param_values: Dict[str, str],
    output_dir: str,
) -> Dict[str, Any]:
    """
    Run a GenePattern module in a local Docker container.

    Layout inside the container:
      /module   – read-only mount of the extracted module files (<libdir>)
      /work     – read-write mount; input files are copied here; outputs land here

    Args:
        zip_path:     Path to the .zip module file.
        param_values: {param_name: value}.  FILE params should be local paths.
        output_dir:   Directory where output files will be copied after the run.

    Returns dict with: job_id, exit_code, stdout, stderr, output_files, command, success.
    """
    from .manifest_parser import extract_module_info

    module_info = extract_module_info(zip_path)
    docker_image = module_info['docker_image']
    command_line = module_info['command_line']
    parameters = module_info['parameters']

    if not docker_image:
        raise ValueError(
            "Module manifest does not specify job.docker.image. "
            "Provide a docker_image argument or fix the manifest."
        )

    # Set up job directories under /tmp/gp-runner/<job-id>/
    job_id = str(uuid.uuid4())[:8]
    job_dir = Path(tempfile.gettempdir()) / 'gp-runner' / job_id
    module_dir = job_dir / 'module'
    work_dir = job_dir / 'work'
    module_dir.mkdir(parents=True)
    work_dir.mkdir(parents=True)

    # Extract module files into module_dir
    extract_module_to_dir(zip_path, str(module_dir))

    # Process parameters: copy FILE inputs to work_dir, remap paths to /work/<name>
    docker_param_values: Dict[str, str] = {}
    for param in parameters:
        pname = param['name']
        value = param_values.get(pname, '').strip()

        if value and param['type'] == 'FILE' and param['mode'] == 'IN':
            src = Path(value).expanduser().resolve()
            if src.exists():
                dst = work_dir / src.name
                shutil.copy2(str(src), str(dst))
                docker_param_values[pname] = f'/work/{src.name}'
            else:
                # Not a local path — pass through (may be a URL or already a container path)
                docker_param_values[pname] = value
        else:
            docker_param_values[pname] = value

    # Build the command string
    cmd_str = build_command(command_line, parameters, docker_param_values, libdir='/module/')

    # Assemble the docker run invocation
    docker_cmd = [
        'docker', 'run', '--rm',
        '-v', f'{module_dir}:/module:ro',
        '-v', f'{work_dir}:/work',
        '-w', '/work',
        docker_image,
    ]

    try:
        docker_cmd.extend(shlex.split(cmd_str))
    except ValueError:
        docker_cmd.extend(cmd_str.split())

    # Execute
    result = subprocess.run(
        docker_cmd,
        capture_output=True,
        text=True,
        timeout=3600,
    )

    # Copy outputs to requested output_dir
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    output_files = []
    for f in sorted(work_dir.iterdir()):
        if f.is_file():
            dst = output_path / f.name
            shutil.copy2(str(f), str(dst))
            output_files.append({
                'name': f.name,
                'path': str(dst),
                'size': f.stat().st_size,
                'suffix': f.suffix.lower(),
            })

    return {
        'job_id': job_id,
        'job_dir': str(job_dir),
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'output_files': output_files,
        'command': ' '.join(docker_cmd),
        'success': result.returncode == 0,
    }


# ─── Output file helpers ──────────────────────────────────────────────────────

_TEXT_SUFFIXES = {'.txt', '.log', '.csv', '.tsv', '.json', '.xml',
                  '.gct', '.res', '.cls', '.odf', '.tab', '.out'}
_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif'}
_HTML_SUFFIXES  = {'.html', '.htm'}
_MIME = {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.gif': 'image/gif', '.bmp': 'image/bmp',
    '.tiff': 'image/tiff', '.tif': 'image/tiff',
}


def get_file_content(file_path: str) -> Optional[str]:
    """Read a text / HTML / SVG file and return its content as a string."""
    path = Path(file_path)
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    if suffix in _TEXT_SUFFIXES | _HTML_SUFFIXES | {'.svg'}:
        try:
            return path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return None
    return None


def get_file_base64(file_path: str) -> Optional[str]:
    """Return base64-encoded content for an image file."""
    path = Path(file_path)
    if not path.exists():
        return None
    if path.suffix.lower() in _IMAGE_SUFFIXES:
        try:
            return base64.b64encode(path.read_bytes()).decode('ascii')
        except Exception:
            return None
    return None


def describe_output_file(file_path: str) -> Dict[str, Any]:
    """
    Return a rich description of an output file suitable for display.

    Returns dict with: name, path, size, type, mime_type, content (or None),
    format ('text'|'html'|'svg'|'base64'|'binary').
    """
    path = Path(file_path)
    if not path.exists():
        return {'error': f'File not found: {file_path}'}

    suffix = path.suffix.lower()
    size = path.stat().st_size
    base = {'name': path.name, 'path': str(path), 'size': size, 'suffix': suffix}

    if suffix in _HTML_SUFFIXES:
        return {**base, 'type': 'html', 'mime_type': 'text/html',
                'format': 'text', 'content': get_file_content(file_path)}

    if suffix == '.svg':
        return {**base, 'type': 'image', 'mime_type': 'image/svg+xml',
                'format': 'svg', 'content': get_file_content(file_path)}

    if suffix in _IMAGE_SUFFIXES:
        mime = _MIME.get(suffix, 'image/png')
        return {**base, 'type': 'image', 'mime_type': mime,
                'format': 'base64', 'content': get_file_base64(file_path)}

    if suffix in _TEXT_SUFFIXES:
        return {**base, 'type': 'text', 'mime_type': 'text/plain',
                'format': 'text', 'content': get_file_content(file_path)}

    return {**base, 'type': 'binary', 'mime_type': 'application/octet-stream',
            'format': 'binary', 'content': None,
            'message': f'Binary file ({size:,} bytes)'}

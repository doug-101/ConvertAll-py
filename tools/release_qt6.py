#!/usr/bin/env python3
"""User-run release: local Linux executable/.deb/AppImage, CI Windows .exe ZIP.

Default: prepare assets only. --draft: create a NON-PUBLISHED GitHub release.
Never installs dependencies, uses sudo, switches branches, pushes, retags,
updates an existing release, or publishes Latest. See doc/RELEASE_LINUX_FR.md.
"""
import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import linux_release as packages
from linux_release import ReleaseError
from release_source import version_from_source

ROOT = Path(__file__).resolve().parents[1]
REPO = 'jojo8356/ConvertAll-py'
BRANCH = 'arena/0adacf84-convertall-py'
WORKFLOW = '.github/workflows/qt6-release.yml'
# The workflow only runs for a commit carrying this marker in its message, so
# ordinary commits stay quiet. Both sides must agree; a test pins that.
CI_MARKER = '[PROD]'
# A push is not instantly visible in the API: without a grace period the script
# used to report "no CI run for this SHA" seconds after a push that had worked.
CI_REGISTRATION_GRACE = 15
CI_REGISTRATION_WAIT = 60
CI_POLL_SECONDS = 5
LOG = None


def command(arguments, *, cwd=ROOT, env=None, timeout=1800, quiet=False):
    arguments = list(map(str, arguments))
    if not quiet:
        print('+ ' + ' '.join(arguments), flush=True)
    try:
        result = subprocess.run(arguments, cwd=cwd, env=env, timeout=timeout,
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace')
    except subprocess.TimeoutExpired as error:
        if LOG is not None:
            # Whatever the command printed before it hung is the only clue that
            # explains why: keep it, a bare "timed out" is not diagnosable.
            with LOG.open('a', encoding='utf-8') as stream:
                stream.write(f'+ {" ".join(arguments)}\nTIMED OUT after {timeout}s\n'
                             + (error.stdout or '') + (error.stderr or '') + '\n')
        raise ReleaseError(f'Command timed out after {timeout}s: {arguments[0]}') from error
    if LOG is not None:
        with LOG.open('a', encoding='utf-8') as stream:
            stream.write('+ ' + ' '.join(arguments) + '\n' + result.stdout + result.stderr + '\n')
    if not quiet or result.returncode:
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
    if result.returncode:
        raise ReleaseError(f'Command failed ({result.returncode}): {arguments[0]}')
    return result.stdout


def github(endpoint, *, missing_ok=False):
    result = subprocess.run(['gh', 'api', endpoint], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', timeout=90)
    if result.returncode:
        if missing_ok and 'HTTP 404' in result.stderr:
            return None
        raise ReleaseError(f'GitHub request failed: {endpoint}\n{result.stderr}')
    return json.loads(result.stdout)


def git(*arguments):
    return command(['git', *arguments], quiet=True).strip()


def require_clean_sha(commit=None):
    if git('branch', '--show-current') != BRANCH:
        raise ReleaseError(f'Run from the session branch: {BRANCH}')
    if git('status', '--porcelain'):
        raise ReleaseError('Working tree is dirty; commit/push changes and revalidate first')
    head = git('rev-parse', 'HEAD')
    if commit is not None and head != commit:
        raise ReleaseError('HEAD changed during release preparation')
    return head


def validate_ci_run(run, commit):
    if (run.get('head_sha') != commit or run.get('head_branch') != BRANCH
            or run.get('path', '').split('@', 1)[0] != WORKFLOW
            or run.get('event') != 'push'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'):
        raise ReleaseError('CI run is not a successful push of the exact current SHA/workflow')


def validate_ci_jobs(jobs):
    expected = {f'Tests {os_name} / Python {version} / Qt6'
                for os_name in ('ubuntu-24.04', 'windows-2022')
                for version in ('3.11', '3.12', '3.13', '3.14')}
    expected |= {f'Bundle {os_name} / Qt6' for os_name in ('ubuntu-24.04', 'windows-2022')}
    expected |= {f'Debian native Qt / {suite}' for suite in ('bookworm', 'trixie')}
    passed = {job['name'] for job in jobs
              if job.get('status') == 'completed' and job.get('conclusion') == 'success'}
    if not expected.issubset(passed):
        hint = (f' CI only runs for commits whose message contains {CI_MARKER}, so a quiet '
                f'push produces no green job at all.') if not passed else ''
        raise ReleaseError(f'Missing/failed CI jobs: {sorted(expected - passed)}.{hint}')


def ci_jobs(run_id):
    return github(f'repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100')['jobs']


def watch_ci(run):
    print(f'Waiting for CI {run["id"]} (no local build has started)...', flush=True)
    try:
        command(['gh', 'run', 'watch', str(run['id']), '--repo', REPO, '--exit-status'])
    except ReleaseError as error:
        print(f'WARNING: {error}\nWARNING: that run did not succeed; its real status is read '
              'from the API below instead of being guessed from the watch command.', flush=True)
    return github(f'repos/{REPO}/actions/runs/{run["id"]}')


def qualifying_ci_run(candidates, commit):
    """Newest completed push of this SHA whose twelve required jobs are green.

    A quiet push only produces skipped jobs, so it can never qualify even if its
    run is reported as successful, and an older green run is never masked by a
    newer quiet one.
    """
    for candidate in candidates:
        if candidate.get('status') != 'completed':
            continue
        try:
            validate_ci_run(candidate, commit)
            validate_ci_jobs(ci_jobs(candidate['id']))
        except ReleaseError:
            continue
        return candidate
    return None


def discover_ci_run(commit, wait):
    """Runs of this SHA, tolerating the delay before GitHub registers a push.

    The API answers seconds before the run exists, so polling happens before the
    "no run" diagnosis, and that diagnosis only appears once the grace period
    really elapsed. The wait is longer with --wait-ci, which already implies
    waiting for CI.
    """
    query = urlencode({'branch': BRANCH, 'head_sha': commit, 'event': 'push', 'per_page': 100})
    deadline = time.monotonic() + (CI_REGISTRATION_WAIT if wait else CI_REGISTRATION_GRACE)
    checks = 0
    while True:
        data = github(f'repos/{REPO}/actions/workflows/{Path(WORKFLOW).name}/runs?{query}')
        candidates = [item for item in data['workflow_runs'] if item['head_sha'] == commit]
        checks += 1
        if candidates:
            return candidates
        if time.monotonic() >= deadline:
            raise ReleaseError(
                f'No CI run for this SHA after {checks} checks and '
                f'{CI_REGISTRATION_WAIT if wait else CI_REGISTRATION_GRACE}s: GitHub registers a '
                f'run a few seconds after a push, and CI only runs for a commit whose message '
                f'contains {CI_MARKER}. Push (or --amend and push) a marked commit, or select an '
                'existing run with --run-id.')
        print(f'No CI run registered for this SHA yet ({checks} check(s); GitHub needs a few '
              f'seconds after a push); checking again in {CI_POLL_SECONDS}s...', flush=True)
        time.sleep(CI_POLL_SECONDS)


def requested_ci_run(args, commit):
    """The CI run a real release needs, or None for a local rehearsal only."""
    if args.local_only:
        if args.draft or args.run_id or args.wait_ci:
            raise ReleaseError('--local-only is a rehearsal: it cannot select or wait for a CI '
                               'run, and it never creates a tag or a release. Drop those options '
                               'to rehearse, or drop --local-only to release.')
        return None
    return select_ci(commit, args.run_id, args.wait_ci)


def select_ci(commit, run_id, wait):
    if run_id:
        run = github(f'repos/{REPO}/actions/runs/{run_id}')
        if (run.get('head_sha') != commit or run.get('head_branch') != BRANCH
                or run.get('path', '').split('@', 1)[0] != WORKFLOW
                or run.get('event') != 'push'):
            raise ReleaseError('The selected CI run belongs to another SHA/branch/workflow')
        if run['status'] != 'completed' and wait:
            run = watch_ci(run)
        validate_ci_run(run, commit)
        validate_ci_jobs(ci_jobs(run['id']))
        return run
    candidates = discover_ci_run(commit, wait)
    run = qualifying_ci_run(candidates, commit)
    if run is None and wait:
        pending = next((item for item in candidates if item.get('status') != 'completed'), None)
        if pending is not None:
            watch_ci(pending)
            # The dictionaries read before the wait are stale now: re-read the list
            # so the diagnosis reports the conclusions GitHub actually has instead of
            # the "queued" status from before the wait.
            candidates = discover_ci_run(commit, wait=False)
            run = qualifying_ci_run(candidates, commit)
    if run is None:
        found = ', '.join(f'{item["id"]}={item.get("status")}/{item.get("conclusion")}'
                          for item in candidates[:5])
        raise ReleaseError(f'No CI run for this SHA has all twelve green jobs ({len(candidates)} '
                           f'run(s) found: {found}). CI only runs for a commit whose message '
                           f'contains {CI_MARKER}, and every one of the twelve jobs must pass.')
    return run


def download_artifact(run, name, destination):
    artifacts = github(f'repos/{REPO}/actions/runs/{run}/artifacts?per_page=100')['artifacts']
    matches = [item for item in artifacts if item['name'] == name and not item['expired']]
    if len(matches) != 1:
        raise ReleaseError(f'Missing/expired/ambiguous CI artifact: {name}')
    destination.mkdir(parents=True, exist_ok=True)
    command(['gh', 'run', 'download', run, '--repo', REPO, '--name', name, '--dir', destination])


def previous_run(reference, commit, builds=None, releases=None):
    """Work and asset directories of an earlier run, for --resume.

    The asset directory name carries the commit it was built from, so artifacts
    of another tree are refused instead of being repackaged under this SHA.
    Nothing is trusted on sight: every recorded hash is re-verified afterwards.
    """
    builds = Path(builds if builds is not None else ROOT / 'build/qt6-release')
    releases = Path(releases if releases is not None else ROOT / 'dist/qt6-release')
    if reference == 'latest':
        candidates = (sorted((path for path in builds.iterdir() if path.is_dir()),
                             key=lambda path: path.name) if builds.is_dir() else [])
        if not candidates:
            raise ReleaseError('No earlier release run to resume; run once without --resume')
        work = candidates[-1]
    else:
        work = builds / reference
        if not (work / 'release.log').is_file():
            raise ReleaseError(f'Not an earlier release run: {work}')
    found = sorted(path.name for path in (releases.iterdir() if releases.is_dir() else [])
                   if path.is_dir() and path.name.endswith('-' + work.name))
    matches = [name for name in found if name == f'{commit}-{work.name}']
    if len(matches) != 1:
        raise ReleaseError(f'Run {work.name} holds {found or "no asset directory"}, not '
                           f'{commit}. A resumed run only reuses artifacts built from the exact '
                           'SHA being released; drop --resume to rebuild everything.')
    return work, releases / matches[0]


def validate_tool_pin(pin):
    if (pin.get('repository') not in ('AppImage/appimagetool', 'AppImage/type2-runtime')
            or type(pin.get('asset_id')) is not int or pin['asset_id'] < 1
            or not re.fullmatch(r'[0-9a-f]{64}', pin.get('sha256', ''))
            or Path(pin.get('name', '')).name != pin.get('name')
            or pin.get('name') in ('', '.', '..')):
        raise ReleaseError('Invalid AppImage tool lock')


def appimage_command(tool, runtime, appdir, output, compression):
    """The pinned builder embeds a zstd-only mksquashfs, not the host tool."""
    if compression != 'zstd':
        raise ReleaseError('Pinned appimagetool supports only zstd compression')
    return [tool, '--runtime-file', runtime, '--comp', compression,
            '--no-appstream', appdir, output]


def fetch_tool(pin, destination, reuse=False):
    """No floating latest download: specific asset ID AND expected SHA-256.

    With `reuse`, a file left by a previous run is accepted only after its
    checksum matches the pin again, so resuming never executes unverified bytes.
    """
    validate_tool_pin(pin)
    path = destination / pin['name']
    if path.exists():
        if not reuse:
            raise ReleaseError(f'Download destination already exists: {path}')
        if packages.sha256(path) != pin['sha256']:
            raise ReleaseError(f'Reused {path.name} does not match the pin; delete it to '
                               'download the pinned asset again')
        require_amd64_elf(path)
        path.chmod(0o755)
        print(f'Reusing pinned {pin["name"]} (checksum re-verified)', flush=True)
        return path
    endpoint = f'repos/{pin["repository"]}/releases/assets/{pin["asset_id"]}'
    print(f'Download pinned {pin["name"]}...', flush=True)
    with path.open('wb') as stream:
        result = subprocess.run(['gh', 'api', endpoint, '-H', 'Accept: application/octet-stream'],
                                cwd=ROOT, stdout=stream, stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        raise ReleaseError('Pinned AppImage asset download failed. It may have been removed; '
                           'do not replace it with an unverified latest binary.\n'
                           + result.stderr.decode('utf-8', errors='replace'))
    if packages.sha256(path) != pin['sha256']:
        raise ReleaseError(f'AppImage tool checksum mismatch: {path.name}; refusing to execute it')
    require_amd64_elf(path)
    path.chmod(0o755)
    return path


def require_amd64_elf(path):
    with Path(path).open('rb') as stream:
        header = stream.read(20)
    if (len(header) < 20 or header[:4] != b'\x7fELF' or header[4:6] != b'\x02\x01'
            or struct.unpack_from('<H', header, 18)[0] != 62):
        raise ReleaseError(f'Expected an x86_64 ELF executable: {path}')


def appimage_payload_offset(path):
    """Offset at which a type 2 runtime expects the squashfs payload.

    The runtime computes it as the end of the ELF, that is the later of the end
    of the section header table and the end of the last section, so any
    fallback extractor applies the same rule. The squashfs magic is verified
    here, which also reports what a failing filesystem serves at that offset.
    """
    with Path(path).open('rb') as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:4] != b'\x7fELF':
            raise ReleaseError(f'Not an ELF AppImage runtime: {path}')
        if header[4:6] != b'\x02\x01':
            raise ReleaseError(f'Unsupported AppImage runtime class in {path}')
        section_offset = struct.unpack_from('<Q', header, 40)[0]
        entry_size = struct.unpack_from('<H', header, 58)[0]
        section_count = struct.unpack_from('<H', header, 60)[0]
        if not (section_offset and entry_size and section_count):
            raise ReleaseError(f'No ELF section table in {path}')
        stream.seek(section_offset + entry_size * (section_count - 1))
        entry = stream.read(entry_size)
        if len(entry) < 64:
            raise ReleaseError(f'Truncated ELF section table in {path}')
        table_end = section_offset + entry_size * section_count
        last_section_end = (struct.unpack_from('<Q', entry, 24)[0]
                            + struct.unpack_from('<Q', entry, 32)[0])
        offset = max(table_end, last_section_end)
        stream.seek(offset)
        magic = stream.read(4)
    if magic != b'hsqs':
        raise ReleaseError(f'No squashfs payload at offset {offset} of {path}: '
                           f'reads returned {magic!r}')
    return offset


def directory_can_execute(directory):
    """Writable is not enough: a noexec mount can hold files it cannot run.

    The AppImage tool and runtime are executed from the scratch directory, so a
    candidate that only accepts writes is worse than useless there.
    """
    if os.name != 'posix':
        return True
    probe = Path(directory) / 'exec-probe'
    try:
        probe.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
        probe.chmod(0o755)
        result = subprocess.run([probe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        probe.unlink(missing_ok=True)
    return result.returncode == 0


def local_scratch_directories(notes=None):
    """Private temporary directories that can also execute what they hold."""
    candidates = [{}]
    shared_memory = Path('/dev/shm')
    if shared_memory.is_dir() and os.access(shared_memory, os.W_OK):
        candidates.append({'dir': shared_memory})
    directories = []
    for arguments in candidates:
        try:
            directory = Path(tempfile.mkdtemp(prefix='convertall-appimage-', **arguments))
        except OSError as error:
            if notes is not None:
                notes.append(f'{arguments.get("dir", "TMPDIR")}: {error}')
            continue
        if directory in directories:
            continue
        if directory_can_execute(directory):
            directories.append(directory)
        elif notes is not None:
            notes.append(f'{directory}: files there cannot be executed (noexec mount?)')
    return directories


def local_scratch_copy(path, expected_sha256=None):
    """Byte-identical private copy of an artifact, verified before it is used."""
    source = Path(path)
    if expected_sha256 is None:
        expected_sha256 = packages.sha256(source)
    errors = []
    for directory in local_scratch_directories(errors):
        target = directory / source.name
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if packages.sha256(target) != expected_sha256:
                raise ReleaseError('copy does not match the source checksum')
            target.chmod(0o755)
            return target
        except (OSError, ReleaseError) as error:
            errors.append(f'{directory}: {error}')
    raise ReleaseError(f'No verified local copy of {source} could be made '
                       f'({"; ".join(errors) or "no usable local directory"})')


def runtime_launch_plan(handlers, claimed_runtime=False):
    """Layers used to exercise the produced AppImage, most direct first.

    A registered binfmt_misc AppImage handler claims the file before its own
    runtime can run, so the layers that execute the image as-is are doomed: they
    failed with a squashfs error on the pinned tool and hung here until the
    command timeout. They are skipped when such a handler is detected, and the
    pinned runtime reads the payload instead -- but only when that runtime is not
    claimed by the same handler (see carries_appimage_magic). With an empty plan
    the payload is exercised from the bytes extracted out of the built image.
    """
    layers = [] if handlers else ['direct', 'local copy']
    if not (handlers and claimed_runtime):
        layers.append('pinned runtime')
    return layers


def extract_squashfs_payload(image, destination, *, required, offset, expected_sha256=None):
    """Read the squashfs payload without running the AppImage runtime.

    Reading the payload ourselves keeps the checksum-pinned bytes as the only
    source of truth when the runtime cannot locate its own filesystem image.
    squashfs-tools is already a documented host requirement for mksquashfs.
    """
    verified = local_scratch_copy(image, expected_sha256)
    payload = verified.parent / 'payload.squashfs'
    with verified.open('rb') as stream, payload.open('wb') as stripped:
        stream.seek(offset)
        shutil.copyfileobj(stream, stripped)
    root = Path(destination) / 'squashfs-root'
    if root.is_dir():
        shutil.rmtree(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    command(['unsquashfs', '-d', root, payload], quiet=True)
    if (root / required).exists():
        return root
    raise ReleaseError(f'no {required} after extracting the payload at offset {offset}')


def extract_appimage(image, destination, *, required, expected_sha256=None, runtime=None,
                     intercepted=False):
    """Extract an AppImage without FUSE, whatever the work tree filesystem does.

    `--appimage-extract` needs no FUSE, but the embedded runtime locates its own
    payload by reading `/proc/self/exe` at the offset it computes from the ELF
    section table, and that lookup fails on some synchronised or otherwise
    exotic mounts ("Failed to open squashfs image"). The pinned bytes are then
    retried from a verified copy on a local disk, through the pinned standalone
    runtime with TARGET_APPIMAGE (which reads the image by path instead of
    /proc/self/exe), and finally by reading the squashfs payload directly.
    No step substitutes another binary, and every attempt works on the very
    bytes that the checksum pins describe. With `intercepted`, the layers that
    execute the image are skipped: a binfmt_misc handler makes them useless, and
    they can hang waiting on that handler.
    """
    image, destination = Path(image), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    scratch_directories = local_scratch_directories(errors)

    def extract_with(program, cwd, env=None):
        command([program, '--appimage-extract'], cwd=cwd, env=env, quiet=True)
        root = Path(cwd) / 'squashfs-root'
        if (root / required).exists():
            return root
        errors.append(f'no {required} in {root}')
        return None

    def attempt(label, program, cwd, env=None):
        try:
            return extract_with(program, cwd, env)
        except ReleaseError as error:
            errors.append(f'{label}: {error}')
            return None

    def so_far():
        """Warnings must not start with an empty reason when nothing failed yet."""
        return f'{" | ".join(errors)}; ' if errors else ''

    if intercepted:
        # Executing the image is pointless here, and it can hang until the
        # command timeout: go straight to the layers that never run it.
        print('Skipping the layers that execute the AppImage itself: a binfmt_misc handler '
              'intercepts it on this machine.', flush=True)
    else:
        root = attempt(f'{image} in place', image, destination)
        if root is not None:
            return root
        try:
            copy = local_scratch_copy(image, expected_sha256)
        except ReleaseError as error:
            # No usable local directory: the remaining layers operate on the very
            # file we already have, so they are still worth trying.
            errors.append(f'local copy: {error}')
        else:
            print(f'WARNING: {so_far()}retrying from {copy}...', flush=True)
            root = attempt('local copy', copy, copy.parent)
            if root is not None:
                return root
    if runtime is not None and Path(runtime).is_file() and scratch_directories:
        # TARGET_APPIMAGE makes the runtime operate on a given file, so its own
        # /proc/self/exe lookup is not involved at all.
        print(f'WARNING: {so_far()}retrying through the pinned runtime...', flush=True)
        root = attempt('pinned runtime', runtime, scratch_directories[0],
                       {**os.environ, 'TARGET_APPIMAGE': str(image)})
        if root is not None:
            return root
    if shutil.which('unsquashfs'):
        try:
            offset = appimage_payload_offset(image)
            print(f'WARNING: {so_far()}reading the payload at offset {offset}...',
                  flush=True)
            return extract_squashfs_payload(image, destination, required=required, offset=offset,
                                            expected_sha256=expected_sha256)
        except (ReleaseError, OSError, ValueError) as error:
            errors.append(f'direct payload read: {error}')
    else:
        errors.append('unsquashfs is not installed (install squashfs-tools)')
    try:
        state = f'{image.stat().st_size} bytes, sha256 now {packages.sha256(image)}'
    except OSError as error:
        state = f'cannot be read back ({error})'
    raise ReleaseError('AppImage could not be extracted: ' + ' | '.join(errors)
                       + f'\n{image}: {state}'
                       + (f' (pinned {expected_sha256})' if expected_sha256 else '')
                       + '\nIf that checksum does not match the pin, or if the work tree lives on a '
                         'shared, synchronised or cloud folder, move the clone to a local disk. '
                         'Checksum pins stay enforced; no unverified tool is ever used.')


BINFMT_DIRECTORY = Path('/proc/sys/fs/binfmt_misc')


def fs_safe(value):
    """A path that can always be printed and serialized, whatever bytes it holds.

    A work tree whose name is not valid UTF-8 reaches Python as lone surrogates;
    printing or json-dumping those raises, which would turn a clear diagnostic
    into a crash, so odd bytes are escaped here.
    """
    return os.fsencode(str(value)).decode('ascii', 'backslashreplace')


# binfmt_misc registrations match three bytes at offset 8 of the file being
# executed: AppImage type 1 and type 2 ('AI\x01', 'AI\x02').
APPIMAGE_MAGIC = (b'AI\x01', b'AI\x02')


def carries_appimage_magic(path):
    """True when a registered binfmt_misc handler would claim this file.

    The pinned runtime is not a neutral tool: AppImage/type2-runtime writes
    b'AI\x02' at offset 8 of the runtime itself (scripts/build-runtime.sh,
    "classic magic bytes ... always do AFTER strip"), so a handler claims it
    exactly like the image that embeds it. Reading the bytes before executing
    them is what separates "this can still launch our payload" from "this waits
    for a handler that cannot read zstd".
    """
    try:
        with Path(path).open('rb') as stream:
            stream.seek(8)
            return stream.read(3) in APPIMAGE_MAGIC
    except OSError:
        return False


def appimage_binfmt_handlers(directory=BINFMT_DIRECTORY):
    """Registrations that intercept AppImage execution, e.g. AppImageLauncher.

    Such a handler claims every file carrying the AppImage magic and parses it
    with its own squashfs reader, which cannot read our zstd payload, so the
    image fails before its own runtime ever runs. Nothing here is changed, it
    is reported so a failed launch can be told apart from a broken artifact.
    """
    handlers = {}
    try:
        entries = sorted(Path(directory).iterdir())
    except OSError:
        return handlers
    for entry in entries:
        if entry.name in ('register', 'status'):
            continue
        try:
            text = entry.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        if 'appimage' in (entry.name + text).lower():
            handlers[entry.name] = text.strip().replace('\n', '; ')
    return handlers


def appimage_environment_report(paths=()):
    """Environment facts that explain a local AppImage failure, kept in the log.

    appimagetool runs its option values through GLib's locale-to-UTF-8
    conversion, which fails with "Option parsing failed: Invalid byte sequence
    in conversion input" when a path is not ASCII and the locale charset is not
    UTF-8. Recording the locale and the paths tells that failure apart from a
    real build problem without another round trip.
    """
    report = {'locale': {name: os.environ.get(name) for name in
                         ('LANG', 'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES', 'LANGUAGE',
                          'TMPDIR', 'PYTHONUTF8', 'PYTHONIOENCODING')},
              'binfmt_misc_appimage_handlers': appimage_binfmt_handlers(),
              'paths': {fs_safe(path): str(path).isascii() for path in paths}}
    print('[appimage] locale: ' + ' '.join(f'{name}={fs_safe(value)}' for name, value in
                                           report['locale'].items() if value is not None), flush=True)
    if report['binfmt_misc_appimage_handlers']:
        print('[appimage] binfmt_misc may intercept AppImages: '
              + '; '.join(f'{name}: {text}' for name, text in
                          report['binfmt_misc_appimage_handlers'].items()), flush=True)
        print('[appimage] stop that handler (for AppImageLauncher: '
              '"sudo systemctl stop appimagelauncherd") to launch AppImages directly.', flush=True)
    else:
        print('[appimage] no binfmt_misc AppImage handler detected', flush=True)
    non_ascii = [path for path, is_ascii in report['paths'].items() if not is_ascii]
    if non_ascii:
        print('[appimage] non-ASCII paths handed to appimagetool: ' + ', '.join(non_ascii),
              flush=True)
    return report


def ascii_build_directory():
    """A local, pure-ASCII directory used to run the pinned AppImage tool.

    GLib converts every argument, so building from ASCII paths keeps the tool
    independent of the locale charset and of the work tree name.
    """
    for directory in local_scratch_directories():
        if str(directory).isascii():
            return directory
    return None


def ascii_tree(root, destination):
    """A local copy of an extracted tool tree, so its path is pure ASCII."""
    root, destination = Path(root), Path(destination)
    if str(root).isascii():
        return root
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(root, destination, symlinks=True, copy_function=shutil.copy2)
    return destination


MAINTAINER_VARIABLE = 'CONVERTALL_MAINTAINER'


def maintainer_identity(provided, environment=None):
    """Public .deb Maintainer field: flag, then environment, then local git identity.

    Git happily invents 'user@machine' for a commit when no identity is configured,
    but that value is never written to the configuration and is a poor public
    address, so the third source only accepts an identity that is really set."""
    if provided:
        return provided
    environment = os.environ if environment is None else environment
    exported = environment.get(MAINTAINER_VARIABLE, '').strip()
    if exported:
        return exported
    def identity(key):
        result = subprocess.run(['git', 'config', '--get', key], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=10)
        if result.returncode not in (0, 1):
            raise ReleaseError(f'Cannot read public Git identity: {key}')
        return result.stdout.strip()
    name, email = identity('user.name'), identity('user.email')
    if not name or not email:
        raise ReleaseError(
            'No public .deb maintainer. Pass --maintainer "Name <email>", or export '
            f'{MAINTAINER_VARIABLE}="Name <email>", or set one identity once with '
            '"git config --global user.name" and "git config --global user.email". '
            'A commit can succeed without those, but a published Debian package must name '
            'a real address, so the release refuses to guess one. Example:\n'
            '  bash release_qt6.sh --wait-ci --draft --maintainer "Your Name <you@example.com>"')
    return f'{name} <{email}>'


def tag_target(tag):
    ref = github(f'repos/{REPO}/git/ref/tags/{tag}', missing_ok=True)
    if ref is None:
        return None
    target = ref['object']
    for _ in range(20):
        if target['type'] == 'commit':
            return target['sha']
        if target['type'] != 'tag':
            break
        target = github(f'repos/{REPO}/git/tags/{target["sha"]}')['object']
    raise ReleaseError('Tag cannot be resolved to an immutable commit')


def check_launch(program, label, work, environment, version, *, bundle=None, prefix=()):
    # Throwaway HOME, always fresh: a resumed run must not inherit the preferences
    # (or the window state) written by the earlier attempt.
    home = Path(tempfile.mkdtemp(prefix=f'{label}-', dir=work))
    env = {**environment, 'HOME': str(home), 'APPDATA': str(home / 'appdata'),
           'XDG_CONFIG_HOME': str(home / 'config'), 'QT_QPA_PLATFORM': 'offscreen',
           'LANG': 'C.UTF-8', 'LC_MESSAGES': 'C', 'PYTHONIOENCODING': 'utf-8'}
    for key in ('PYTHONPATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH',
                'LD_LIBRARY_PATH', 'APPDIR', 'APPIMAGE'):
        env.pop(key, None)
    def launch(*arguments):
        return command([program, *prefix, *arguments], cwd=home, env=env, timeout=180, quiet=True)
    runtime = json.loads(launch('--runtime-info'))
    from check_bundle import validate_runtime_info
    validate_runtime_info(runtime)
    if runtime['version'] != version:
        raise ReleaseError(f'{label}: wrong application version')
    if bundle is not None and not Path(runtime['qt_translations_path']).resolve().is_relative_to(bundle.resolve()):
        raise ReleaseError(f'{label}: Qt translations escaped the packaged bundle')
    text = launch('-q', '1', 'in', 'cm')
    if abs(float(text.split('=', 1)[1].strip().split()[0]) - 2.54) > 1e-10:
        raise ReleaseError(f'{label}: wrong packaged conversion')
    if launch('--test-all').count('All units pass tests') != 7:
        raise ReleaseError(f'{label}: not all seven packaged catalogues passed')
    if 'GUI smoke test passed' not in launch('--gui-smoke-test'):
        raise ReleaseError(f'{label}: packaged Qt widgets failed')
    print(f'PASS {label}: runtime, conversion, 7 catalogues, GUI offscreen', flush=True)
    return {'status': 'PASS', 'runtime': runtime, 'qt_platform': 'offscreen'}


def test_summary(validation_path=None, junit_path=None, coverage_path=None):
    results = ROOT / 'build/test-results'
    report = json.loads((validation_path or results / 'validation.json').read_text(encoding='utf-8'))
    junit = ET.parse(junit_path or results / 'junit.xml').getroot()
    suites = [junit] if junit.tag == 'testsuite' else junit.findall('testsuite')
    counts = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ('tests', 'failures', 'errors', 'skipped')}
    coverage = json.loads((coverage_path or results / 'coverage.json').read_text(encoding='utf-8'))
    return report, {**counts, 'coverage_percent': coverage['totals']['percent_covered']}


def build_release(args):
    global LOG
    if sys.platform != 'linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise ReleaseError('Build .deb/AppImage on Linux x86_64; Windows executables come from native CI')
    os_release = platform.freedesktop_os_release()
    if not {'debian', 'ubuntu'}.intersection(
            {os_release.get('ID', ''), *os_release.get('ID_LIKE', '').split()}):
        raise ReleaseError('The .deb builder currently targets Debian/Ubuntu family hosts')
    for executable in ('git', 'gh', 'dpkg-deb', 'readelf', 'mksquashfs', 'desktop-file-validate'):
        if shutil.which(executable) is None:
            raise ReleaseError(f'Missing {executable}; see doc/RELEASE_LINUX_FR.md (no auto-install)')
    if not (3, 11) <= sys.version_info[:2] <= (3, 14):
        raise ReleaseError('Use the pinned Python 3.11–3.14 release venv')
    for name, required in (('PyInstaller', '6.22.3'), ('pyinstaller-hooks-contrib', '2026.8')):
        if metadata.version(name) != required:
            raise ReleaseError(f'Wrong {name}; install requirements-build.txt yourself')
    commit = require_clean_sha()
    version = version_from_source((ROOT / 'source/convertall.py').read_text(encoding='utf-8'))
    tag = 'v' + version
    maintainer = maintainer_identity(args.maintainer)
    # Validate user-supplied headers before any long-running command.
    packages.deb_control(version, maintainer, 1)
    # The .deb must be tested with Debian's shared runtime, never the wheel venv.
    command(['/usr/bin/python3', '-E', '-s', ROOT / 'tools/build_deb.py', '--probe-system'], quiet=True)
    lock = json.loads((ROOT / 'tools/appimage-lock.json').read_text(encoding='utf-8'))
    if lock.get('architecture') != 'x86_64':
        raise ReleaseError('AppImage tool architecture mismatch')
    if lock.get('compression') != 'zstd':
        raise ReleaseError('Pinned appimagetool supports only zstd compression')
    validate_tool_pin(lock['appimagetool'])
    validate_tool_pin(lock['runtime'])
    existing_target = tag_target(tag)
    if existing_target is not None and existing_target != commit:
        raise ReleaseError(f'{tag} already targets another SHA. Never retarget it; choose a new version.')
    if args.draft and github(f'repos/{REPO}/releases/tags/{tag}', missing_ok=True) is not None:
        raise ReleaseError(f'Release {tag} already exists. No overwrite/clobber is performed.')
    # Decide before anything reads `run`: a rehearsal resolves no CI run at all.
    run = requested_ci_run(args, commit)
    if run is None:
        print('LOCAL REHEARSAL: no CI gate, no tag and no release are involved. The real release '
              f'still requires a push whose message contains {CI_MARKER} and all twelve CI jobs '
              'green.', flush=True)
    if args.resume is None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
        work = ROOT / 'build/qt6-release' / stamp
        assets = ROOT / 'dist/qt6-release' / (commit + '-' + stamp)
        work.mkdir(parents=True)
        assets.mkdir(parents=True)
        resumed = False
    else:
        work, assets = previous_run(args.resume, commit)
        resumed = True
        print(f'Resuming run {work.name}: steps 1-3 are not rebuilt, every recorded hash is '
              'verified again below', flush=True)
    LOG = work / 'release.log'
    epoch = int(git('show', '-s', '--format=%ct', commit))
    environment = {**os.environ, 'SOURCE_DATE_EPOCH': str(epoch), 'QT_API': 'pyqt6',
                   'QT_QPA_PLATFORM': 'offscreen', 'PYTHONIOENCODING': 'utf-8'}
    for key in ('APPDIR', 'APPIMAGE', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        environment.pop(key, None)
    print(f'SHA={commit}\nCI={run["html_url"] if run else "none (local rehearsal)"}'
          f'\nAssets={assets}', flush=True)

    print('\n[1/7] Full local source QA (clean SHA, pinned profile, coverage)', flush=True)
    if resumed:
        print('Reusing the QA this run recorded; the SHA-bound checks below still run.', flush=True)
        for name in ('source-validation.json', 'junit.xml', 'coverage.json'):
            if not (assets / name).is_file():
                raise ReleaseError(f'Run {work.name} has no recorded {name}: it failed before the '
                                   'QA finished, so run once without --resume')
        source_report, tests = test_summary(assets / 'source-validation.json', assets / 'junit.xml',
                                            assets / 'coverage.json')
    else:
        command([sys.executable, ROOT / 'tools/validate_release.py', '--require-clean'],
                env=environment)
        source_report, tests = test_summary()
        shutil.copyfile(ROOT / 'build/test-results/validation.json', assets / 'source-validation.json')
        shutil.copyfile(ROOT / 'build/test-results/junit.xml', assets / 'junit.xml')
        shutil.copyfile(ROOT / 'build/test-results/coverage.json', assets / 'coverage.json')
    if source_report.get('commit') != commit or source_report.get('release_eligible') is not True:
        raise ReleaseError('Local source report does not certify the current clean SHA')

    print('\n[2/7] Local Linux bundle (do not impose Ubuntu CI GLIBC on Debian)', flush=True)
    bundle = work / 'dist/convertall'
    linux_report = work / 'linux-bundle-validation.json'
    if resumed:
        print('Reusing the bundle this run recorded: its report is re-hashed file by file.',
              flush=True)
        for path in (bundle, bundle / 'convertall', linux_report,
                     bundle / 'RELEASE-INFO.json'):
            if not path.exists():
                raise ReleaseError(f'Run {work.name} has no {path.relative_to(work)} to resume '
                                   'from; run once without --resume')
        base_report = json.loads(linux_report.read_text(encoding='utf-8'))
        # The bundle also holds what packaging adds after the report was written:
        # the wheel notices and RELEASE-INFO.json are the only tolerated extras.
        packages.verify_bundle_report(bundle, base_report, commit, version,
                                      extra_prefixes=('doc/third-party/', 'RELEASE-INFO.json'))
        require_amd64_elf(bundle / 'convertall')
        info = json.loads((bundle / 'RELEASE-INFO.json').read_text(encoding='utf-8'))
        if info.get('version') != version or info.get('source_commit') != commit:
            raise ReleaseError('The reused bundle is not bound to this SHA/version')
        if run is not None and info.get('ci_run') != run['id']:
            raise ReleaseError(f'The reused bundle is bound to CI run {info.get("ci_run")}, but '
                               f'run {run["id"]} was selected; drop --resume, or pass --run-id '
                               f'{info.get("ci_run")}')
        glibc = info.get('glibc_required')
        if not isinstance(glibc, str) or not glibc:
            raise ReleaseError('The reused bundle has no recorded GLIBC requirement')
        notices = packages.collect_notices(bundle)  # rewrites the very same notices
    else:
        command([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                 '--distpath', work / 'dist', '--workpath', work / 'pyinstaller',
                 ROOT / 'source/convertall.spec'], env=environment)
        require_amd64_elf(bundle / 'convertall')
        command([sys.executable, ROOT / 'tools/check_bundle.py', bundle, '--report', linux_report],
                env=environment)
        base_report = json.loads(linux_report.read_text(encoding='utf-8'))
        packages.verify_bundle_report(bundle, base_report, commit, version)
        shutil.copyfile(linux_report, assets / 'linux-bundle-validation.json')
        glibc = packages.glibc_requirement(bundle, lambda path: command(
            ['readelf', '--version-info', path], quiet=True))
        notices = packages.collect_notices(bundle)
        # Include a CPython notice where supplied by the build host (not a legal guarantee).
        python_notice = (Path('/usr/share/doc')
                         / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'copyright')
        if python_notice.is_file():
            shutil.copyfile(python_notice, bundle / 'doc/third-party/CPython-copyright')
        info = {'version': version, 'source_commit': commit,
                'ci_run': run['id'] if run else None, 'architecture': 'x86_64',
                'glibc_required': glibc, 'runtime': base_report['runtime']}
        packages.write_file(bundle / 'RELEASE-INFO.json', json.dumps(info, indent=2) + '\n')

    print('\n[3/7] Portable executable archive and Debian package', flush=True)
    portable_name = f'ConvertAll-{version}-qt6-linux-x86_64'
    portable = work / portable_name
    tarball = assets / (portable_name + '.tar.gz')
    tar_extract = work / 'portable-extracted'
    deb = assets / f'convertall_{version}-1_all.deb'
    if resumed:
        print('Re-extracting the shipped tarball to re-run its payload and launch checks.',
              flush=True)
        for path in (tarball, deb, assets / 'native-deb-validation.json'):
            if not path.is_file():
                raise ReleaseError(f'Run {work.name} has no {path.name} to resume from; run once '
                                   'without --resume')
        tar_extract.mkdir(parents=True, exist_ok=True)
        packages.extract_own_tar(tarball, tar_extract)
    else:
        packages.copy_bundle(bundle, portable)
        packages.make_tar(portable, tarball, epoch)
        tar_extract.mkdir()
        packages.extract_own_tar(tarball, tar_extract)
    packages.verify_payload(tar_extract / portable_name, base_report['bundle_sha256'])
    checks = {'portable': check_launch(tar_extract / portable_name / 'convertall', 'portable', work,
                                      environment, version, bundle=tar_extract / portable_name)}
    if not resumed:
        command(['/usr/bin/python3', '-E', '-s', ROOT / 'tools/build_deb.py',
                 '--output-dir', assets, '--work-dir', work / 'native-deb',
                 '--maintainer', maintainer], env=environment)
    checks['deb'] = json.loads((assets / 'native-deb-validation.json').read_text(encoding='utf-8'))
    if (checks['deb'].get('status') != 'PASS' or checks['deb'].get('source_commit') != commit
            or checks['deb'].get('bundled_runtime') is not False
            or checks['deb'].get('package_sha256') != packages.sha256(deb)):
        raise ReleaseError('Native Debian package did not pass for this exact SHA')

    print('\n[4/7] AppImage with checksum-pinned builder AND runtime (no FUSE for tests)', flush=True)
    tools = work / 'appimage-tools'
    tools.mkdir(exist_ok=True)
    tool_image = fetch_tool(lock['appimagetool'], tools, reuse=resumed)
    runtime = fetch_tool(lock['runtime'], tools, reuse=resumed)
    # Everything the pinned tool reads or writes is kept in a local ASCII directory:
    # GLib converts each argument through the locale charset, so a work tree under a
    # non-ASCII name (or a non-UTF-8 locale) aborts appimagetool with "Option parsing
    # failed: Invalid byte sequence in conversion input" before it does any work.
    build_dir = ascii_build_directory() or work
    if not str(build_dir).isascii():
        print('WARNING: no ASCII build directory is available; appimagetool may refuse the '
              'paths it is given below.', flush=True)
    checks['appimage_environment'] = appimage_environment_report(
        [tool_image, runtime, build_dir, assets])
    # A registered handler claims every AppImage on this machine, so from here on
    # the layers that execute such a file are skipped instead of hanging.
    handlers = checks['appimage_environment']['binfmt_misc_appimage_handlers']
    # The pinned runtime carries the AppImage magic itself, so a registered handler
    # claims it exactly like the image it builds: executing it there waits for a
    # handler that cannot read zstd until the command timeout (observed locally, on a
    # host with AppImageLauncher). It is therefore never executed below, and the
    # extraction reads the payload with unsquashfs instead.
    claimed_runtime = bool(handlers) and carries_appimage_magic(runtime)
    if claimed_runtime:
        print('WARNING: the pinned runtime carries the AppImage magic at offset 8 as well, so '
              'the registered handler (' + ', '.join(handlers) + ') claims it exactly like the '
              'image it builds; it is not executed. For a real launch test, disable that '
              'handler first:\n  sudo systemctl stop appimagelauncherd\n'
              + '\n'.join(f'  echo -1 | sudo tee /proc/sys/fs/binfmt_misc/{name}'
                          for name in handlers), flush=True)
    tool_root = extract_appimage(tool_image, build_dir / 'tool-extracted', required='AppRun',
                                expected_sha256=lock['appimagetool']['sha256'],
                                runtime=None if claimed_runtime else runtime,
                                intercepted=bool(handlers))
    tool = ascii_tree(tool_root, build_dir / 'tool') / 'AppRun'
    appdir = packages.stage_appdir(bundle, build_dir / 'ConvertAll.AppDir', ROOT)
    command(['desktop-file-validate', appdir / 'convertall.desktop'])
    runtime_argument = build_dir / 'runtime-x86_64'
    shutil.copyfile(runtime, runtime_argument)
    if packages.sha256(runtime_argument) != lock['runtime']['sha256']:
        raise ReleaseError('Copied runtime does not match the lock file checksum')
    image = assets / f'ConvertAll-{version}-x86_64.AppImage'
    built = build_dir / image.name
    command(appimage_command(tool, runtime_argument, appdir, built, lock['compression']),
            cwd=build_dir, env={**environment, 'ARCH': 'x86_64', 'VERSION': version,
                                'LC_ALL': 'C.UTF-8'})
    if not built.is_file():
        raise ReleaseError(f'appimagetool reported success but {built} is missing')
    shutil.move(built, image)
    image.chmod(0o755)
    # Then exercise the actual AppImage runtime, not just the uncompressed AppDir.
    # The runtime reads its payload through /proc/self/exe and unpacks itself into
    # TMPDIR, so both are pointed at a verified local directory when one exists, an
    # unreadable work tree is retried from a byte-identical local copy, and, when no
    # binfmt_misc handler claims those files, the pinned runtime reads the very bytes
    # the AppImage embeds.
    scratch = local_scratch_directories()
    runtime_environment = {**environment, 'TMPDIR': str(scratch[0])} if scratch else environment
    prefix = ('--appimage-extract-and-run',)
    plan = runtime_launch_plan(handlers, claimed_runtime)
    if 'direct' not in plan:
        print('WARNING: an AppImage binfmt_misc handler (' + ', '.join(handlers)
              + ') intercepts every AppImage here, so running the built file directly is '
              'skipped.', flush=True)
    launcher, direct_error = None, None
    for layer in plan:
        try:
            if layer == 'direct':
                checks['appimage_runtime'] = check_launch(image, 'appimage-runtime', work,
                                                          runtime_environment, version,
                                                          prefix=prefix)
                launcher = 'direct'
            elif layer == 'local copy':
                print('WARNING: retrying the AppImage runtime check from a verified local '
                      'copy...', flush=True)
                checks['appimage_runtime'] = check_launch(local_scratch_copy(image),
                                                          'appimage-runtime-local', work,
                                                          runtime_environment, version,
                                                          prefix=prefix)
                launcher = 'verified local copy'
            else:
                print('WARNING: the built image cannot be executed on this host; running the '
                      'same payload through the pinned runtime with TARGET_APPIMAGE...',
                      flush=True)
                checks['appimage_runtime'] = check_launch(
                    runtime, 'appimage-runtime-pinned', work,
                    {**runtime_environment, 'TARGET_APPIMAGE': str(image)}, version, prefix=prefix)
                launcher = 'pinned runtime with TARGET_APPIMAGE'
            break
        except ReleaseError as error:
            direct_error = direct_error or str(error)
            print(f'WARNING: {error}', flush=True)
    extracted_app = extract_appimage(image, work / 'appimage-extracted',
                                     required='usr/lib/convertall',
                                     runtime=None if claimed_runtime else runtime,
                                     intercepted=bool(handlers))
    packages.verify_payload(extracted_app / 'usr/lib/convertall', base_report['bundle_sha256'])
    checks['appimage_apprun'] = check_launch(extracted_app / 'AppRun', 'appimage-apprun', work,
                                            environment, version, bundle=extracted_app / 'usr/lib/convertall')
    if launcher is None:
        # Nothing carrying the AppImage magic can be executed here, so the payload read
        # out of the built image is the proof this host can honestly give: unsquashfs
        # reads the very bytes appimagetool wrote, and the extracted AppRun was just run
        # above -- with the app, the seven catalogues and the offscreen GUI.
        launcher = 'extracted payload (the image bytes were read, never executed)'
        checks['appimage_runtime'] = {**checks['appimage_apprun'], 'launcher': launcher,
                                      'direct_execution_error': direct_error or
                                      'no layer that executes an AppImage is available here'}
    elif launcher != 'direct':
        checks['appimage_runtime'] = {**checks['appimage_runtime'], 'launcher': launcher,
                                      'direct_execution_error': direct_error}
    if launcher != 'direct':
        print('WARNING: the built AppImage could not be launched directly on this machine; its '
              f'payload and runtime were exercised through the {launcher}. Check for an '
              'AppImage binfmt_misc handler (see [appimage] above) and confirm a double-click '
              'launch in the acceptance VM before publishing Latest.', flush=True)

    if run is None:
        print('\n[5/7] Skipped: the Windows executables and the source archive come from CI, and '
              'this is a local rehearsal.', flush=True)
        print('[6/7] Skipped: provenance/notes describe a real release.', flush=True)
        print('[7/7] Skipped: no tag and no release are created by a rehearsal.', flush=True)
        rehearsal = {'status': 'PASS', 'source_commit': commit, 'ci_run': None,
                     'warning': 'NOT a release: local rehearsal only, no CI gate',
                     'checks': checks, 'source_tests': tests,
                     'assets': {path.name: {'sha256': packages.sha256(path),
                                            'bytes': path.stat().st_size}
                                for path in sorted(assets.iterdir()) if path.is_file()}}
        report = assets / 'local-rehearsal.json'
        packages.write_file(report, json.dumps(rehearsal, indent=2, ensure_ascii=False) + '\n')
        print(f'\nRehearsal PASS: bundle, portable, .deb and AppImage checks ran locally.\n'
              f'Assets: {assets}\nReport: {report}\nLog: {LOG}\n'
              'Nothing was tagged or published: the real release still needs a marked push with '
              'all twelve CI jobs green (bash release_qt6.sh --wait-ci --draft).', flush=True)
        return assets

    print('\n[5/7] Exact CI source archive and Windows executables (complete onedir ZIP)', flush=True)
    source_input = work / 'ci-source'
    download_artifact(run['id'], f'qt6-source-{commit}', source_input)
    for path in packages.verify_source_archive(source_input, version, commit):
        shutil.copyfile(path, assets / path.name)
    windows_input, windows_report_dir = work / 'ci-windows', work / 'ci-windows-report'
    download_artifact(run['id'], 'qt6-bundle-windows-2022', windows_input)
    download_artifact(run['id'], 'qt6-bundle-report-windows-2022', windows_report_dir)
    report_path = windows_report_dir / 'bundle-validation.json'
    windows_report = json.loads(report_path.read_text(encoding='utf-8'))
    packages.verify_bundle_report(windows_input, windows_report, commit, version)
    for name in ('convertall.exe', 'convertall_dos.exe'):
        with (windows_input / name).open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ReleaseError(f'Not a Windows executable: {name}')
    windows_zip = assets / f'ConvertAll-{version}-qt6-windows-x86_64.zip'
    windows_prefix = f'ConvertAll-{version}-qt6-windows-x86_64'
    packages.make_windows_zip(windows_input, windows_zip, windows_prefix, epoch)
    import zipfile
    with zipfile.ZipFile(windows_zip) as archive:
        expected_names = {f'{windows_prefix}/{name}' for name in windows_report['bundle_sha256']}
        if set(archive.namelist()) != expected_names or archive.testzip() is not None:
            raise ReleaseError('Windows portable ZIP integrity/file list mismatch')
    shutil.copyfile(report_path, assets / 'windows-bundle-validation.json')

    print('\n[6/7] Provenance, checksums and observed release notes', flush=True)
    require_clean_sha(commit)
    manifest = {**info, 'ci_url': run['html_url'], 'packager_commit': commit,
                'build_host': platform.platform(), 'build_os_release': os_release,
                'build_python': sys.version, 'source_tests': tests, 'package_checks': checks,
                'appimage_lock': lock, 'wheel_notices': notices,
                'debian_profile': {'architecture': 'all', 'bundled_runtime': False,
                                   'depends': list(packages.DEBIAN_DEPENDENCIES)},
                'manual_acceptance': 'NOT CERTIFIED: real desktop/DPI/GPU, apt install/remove, Windows, licences',
                'assets': {path.name: {'sha256': packages.sha256(path), 'bytes': path.stat().st_size}
                           for path in sorted(assets.iterdir()) if path.is_file()}}
    packages.write_file(assets / 'release-provenance.json', json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    notes = (f'# ConvertAll {version} — Python / Qt6\n\n'
             f'Source SHA: `{commit}`\nCI: {run["html_url"]}\n\n'
             f'Local Linux QA: {tests["tests"]} tests, {tests["failures"]} failures, '
             f'{tests["errors"]} errors, {tests["skipped"]} skips; '
             f'combined coverage {tests["coverage_percent"]:.2f}%.\n'
             'CI: Ubuntu/Windows × Python 3.11–3.14 and both native bundles passed.\n\n'
             '## Downloads\n'
             f'- `{tarball.name}`: Linux executable AND all private Qt/Python resources.\n'
             f'- `{deb.name}`: small Debian architecture-all package; Python/PyQt6/Qt supplied by apt Depends.\n'
             f'- `{image.name}`: Linux x86_64 AppImage; `chmod +x` before running.\n'
             f'- `{windows_zip.name}`: extract the WHOLE directory, then run `convertall.exe`.\n'
             f'- `ConvertAll-{version}-qt6-source.tar.gz`: exact CI application source.\n\n'
             f'Portable/AppImage minimum ELF GLIBC requirement detected: **{glibc}**. '
             'This does not apply to the source-only .deb: apt manages its shared runtime.\n'
             'Desktop/graphics system libraries are still required; not universal Linux compatibility.\n'
             'AppImage note: the payload is zstd-compressed (the pinned builder offers no other '
             'codec) and AppImageLauncher (last release 2019) cannot read zstd AppImages, so with '
             "it installed the double-click fails with \"This doesn't look like a squashfs "
             'image\". Those users should use the portable tarball or the .deb, or stop the '
             'AppImageLauncher daemon.\n'
             'Portable/AppImage and native Debian runtime, conversions, 7 catalogues and offscreen GUI passed locally.\n'
             'Debian native Qt regressions/package checks passed in Bookworm and Trixie CI.\n'
             'SHA256SUMS and JSON reports bind these assets to the source/CI/build host.\n\n'
             '## Review before publishing\n'
             'Real desktop/DPI/GPU and apt install/upgrade/remove still require manual acceptance.\n'
             'Windows ZIP is NOT an Inno installer. No macOS build is provided.\n'
             'Review GPLv3 and all third-party notices/corresponding-source obligations. '
             'Collected wheel notices are not a complete legal inventory.\n'
             'Qt5 v0.8.1 is unchanged. This release is a draft, not automatically Latest.\n')
    launcher = checks.get('appimage_runtime', {}).get('launcher', 'direct')
    if launcher != 'direct':
        notes += (
            f'\n## AppImage acceptance required\n'
            f'This build host could not launch the produced AppImage itself; the payload was '
            f'exercised through the {launcher} instead (see appimage_runtime in '
            f'release-provenance.json). Confirm a real double-click launch, desktop/DPI and GPU '
            f'behaviour in a clean environment, and check for an AppImage binfmt_misc handler '
            f'before publishing Latest.\n')
    packages.write_file(assets / 'RELEASE_NOTES.md', notes)
    payloads = sorted(path for path in assets.iterdir() if path.is_file())
    packages.write_file(assets / 'SHA256SUMS', ''.join(
        f'{packages.sha256(path)}  {path.name}\n' for path in payloads))
    print(f'\nLinux baseline: GLIBC >= {glibc}\nAssets: {assets}\nLog: {LOG}', flush=True)

    print('\n[7/7] GitHub draft (only with --draft; never Latest)', flush=True)
    if args.draft:
        require_clean_sha(commit)
        current_target = tag_target(tag)
        if current_target is not None and current_target != commit:
            raise ReleaseError('Tag changed while packaging; refusing to publish any draft')
        if github(f'repos/{REPO}/releases/tags/{tag}', missing_ok=True) is not None:
            raise ReleaseError('Release was created while packaging; no overwrite is performed')
        if current_target is None:
            command(['gh', 'api', '--method', 'POST', f'repos/{REPO}/git/refs',
                     '-f', f'ref=refs/tags/{tag}', '-f', f'sha={commit}'])
        if tag_target(tag) != commit:
            raise ReleaseError('Tag verification failed before draft creation')
        command(['gh', 'release', 'create', tag, '--repo', REPO, '--verify-tag', '--draft',
                 '--title', f'ConvertAll {version} — Qt6', '--notes-file', assets / 'RELEASE_NOTES.md',
                 *sorted(path for path in assets.iterdir() if path.is_file())])
        print(f'Draft created: https://github.com/{REPO}/releases/tag/{tag}\n'
              'Review/manual acceptance required. NOTHING was published as Latest.', flush=True)
    else:
        print('Assets ready locally; no tag/release created. Use --draft to prepare a GitHub draft.', flush=True)
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true', help='create a non-published GitHub draft after all checks')
    parser.add_argument('--wait-ci', action='store_true', help='wait for the current SHA CI before local builds')
    parser.add_argument('--run-id', type=int, help='use this exact successful CI push run (same SHA required)')
    parser.add_argument('--local-only', action='store_true',
                        help='rehearsal: run the local steps (bundle, portable, .deb, AppImage) '
                             'without a CI run, and never create a tag or a release')
    parser.add_argument('--resume', nargs='?', const='latest', metavar='STAMP',
                        help='reuse the re-verified artifacts of an earlier run of this exact '
                             'SHA (default: the most recent run) instead of rebuilding steps 1-3')
    parser.add_argument('--maintainer', help='public .deb Maintainer: "Name <email>"; default: '
                        f'${MAINTAINER_VARIABLE}, then the configured git identity')
    args = parser.parse_args()
    try:
        build_release(args)
        return 0
    except (ReleaseError, OSError, ValueError, KeyError, TypeError,
            metadata.PackageNotFoundError, subprocess.TimeoutExpired) as error:
        print(f'Release preparation FAILED: {error}', file=sys.stderr)
        if LOG is not None:
            print(f'Log retained: {LOG}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; no automatic cleanup, retry into a fresh output directory.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())

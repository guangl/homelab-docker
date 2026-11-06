"""Fail-closed, local subtitle fallback core (Python 3.8+, standard library).

NOT a Sublarr scheduler/plugin integration. provider_query(language, episode_id)
must return a sequence of fully identified, already acquired local Candidates,
or raise on failure (None is NOT an empty result). prepare_source(candidate)
must return UTF-8 SRT bytes: downloading, embedded extraction and ASS/SSA/VTT
normalization belong to that adapter. Original sources must not be changed.
The injected backend exposes translate_batch(lines, source_language, "zh").
No credentials, network calls, video edits or automatic source cleanup occur here.
"""
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple


class FallbackError(Exception):
    """A failed prerequisite; callers must not treat this as no results."""


class AcquisitionError(FallbackError):
    pass


class SourceChangedError(FallbackError):
    pass


class TranslationError(FallbackError):
    pass


class ExistingChineseError(FallbackError):
    pass


@dataclass(frozen=True)
class Candidate:
    language: Optional[str]
    location: Optional[str]  # embedded or sidecar; never a language rank
    subtitle_type: Optional[str]  # text or image
    format: Optional[str]  # srt/ass/ssa/vtt, or pgs/vobsub for image
    coverage: Optional[str]  # full; signs/forced/unknown are ineligible
    episode_id: Optional[str]  # exact, trusted identity supplied by adapter
    source_path: Optional[str]  # acquired sidecar or embedded source container
    source_exists: Optional[bool]
    stream_index: Optional[int] = None  # absolute ffprobe index for embedded text


@dataclass(frozen=True)
class Selection:
    status: str  # skip_chinese, selected, no_source
    candidate: Optional[Candidate] = None


_LANGUAGES = {
    "zh": "zh", "zho": "zh", "chi": "zh", "zh-cn": "zh",
    "zh-tw": "zh", "zh-hans": "zh", "zh-hant": "zh",
    "ja": "ja", "jpn": "ja", "en": "en", "eng": "en",
}
_TEXT_FORMATS = frozenset(("srt", "ass", "ssa", "vtt"))
_IMAGE_FORMATS = frozenset(("pgs", "vobsub"))


def _language(candidate: Candidate) -> Optional[str]:
    value = candidate.language
    return _LANGUAGES.get(value.lower()) if isinstance(value, str) else None


def _eligible(candidate: Candidate, episode_id: str) -> bool:
    if not isinstance(candidate, Candidate):
        return False
    if (not episode_id or candidate.episode_id != episode_id
            or candidate.location not in ("embedded", "sidecar")
            or candidate.coverage != "full"
            or candidate.source_exists is not True
            or _language(candidate) is None
            or not candidate.source_path):
        return False
    formats = (_TEXT_FORMATS if candidate.subtitle_type == "text" else
               _IMAGE_FORMATS if candidate.subtitle_type == "image" else ())
    return candidate.format in formats and Path(candidate.source_path).is_file()


def select_candidates(candidates: Sequence[Candidate], episode_id: str) -> Selection:
    """Any eligible Chinese skips; otherwise all Japanese text precedes English.

    A full Chinese image track already serves Chinese and therefore skips; image
    tracks are never translation inputs. Unknown metadata is never guessed from
    filenames. Within one language preserve input order, irrespective of format
    and embedded/sidecar location.
    """
    eligible = [c for c in candidates if _eligible(c, episode_id)]
    for candidate in eligible:
        if _language(candidate) == "zh":
            return Selection("skip_chinese", candidate)
    for language in ("ja", "en"):
        for candidate in eligible:
            if _language(candidate) == language and candidate.subtitle_type == "text":
                return Selection("selected", candidate)
    return Selection("no_source")


def acquire_source(episode_id: str, existing: Sequence[Candidate],
                   provider_query: Callable[[str, str], Sequence[Candidate]]) -> Selection:
    """Query zh -> ja -> en, stopping only on an eligible source or Chinese.

    Existing Japanese/English cannot bypass the Chinese query. A query is a
    successful empty sequence or a successful sequence of local candidates;
    exceptions, None and malformed responses abort instead of falling through.
    For each foreign language query first, then consider existing + acquired.
    """
    initial = select_candidates(existing, episode_id)
    if initial.status == "skip_chinese":
        return initial
    pool = list(existing)
    for language in ("zh", "ja", "en"):
        try:
            response = provider_query(language, episode_id)
            if not isinstance(response, (list, tuple)) or any(
                    not isinstance(c, Candidate) for c in response):
                raise ValueError("provider must return a list/tuple of Candidates")
            if any(_language(c) not in (None, language) for c in response):
                raise ValueError("provider returned a different requested language")
        except Exception as exc:
            raise AcquisitionError("%s query failed: %s" % (language, exc)) from exc
        pool.extend(response)
        selection = select_candidates(pool, episode_id)
        if selection.status == "skip_chinese":
            return selection
        if language != "zh" and selection.status == "selected":
            if _language(selection.candidate) == language:
                return selection
    return select_candidates(pool, episode_id)


def _digest(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_source(path: str, expected: str) -> None:
    try:
        actual = _digest(path)
    except OSError as exc:
        raise SourceChangedError("source disappeared or became unreadable") from exc
    if actual != expected:
        raise SourceChangedError("source hash changed; refusing publication")


_TIMESTAMP = re.compile(
    r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> "
    r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})(?:[ \t]+.*)?$")


def _text_positions(lines: Sequence[str]) -> Sequence[int]:
    positions = []
    cursor = 0
    while cursor < len(lines):
        if not lines[cursor].rstrip("\r\n"):
            cursor += 1
            continue
        if not lines[cursor].rstrip("\r\n").isdigit():
            raise TranslationError("invalid SRT cue index")
        cursor += 1
        if cursor >= len(lines):
            raise TranslationError("missing SRT timeline")
        match = _TIMESTAMP.fullmatch(lines[cursor].rstrip("\r\n"))
        if match is None:
            raise TranslationError("invalid SRT timeline")
        values = tuple(int(v) for v in match.groups())
        if values[:4] > values[4:]:
            raise TranslationError("SRT timeline runs backwards")
        cursor += 1
        start = cursor
        while cursor < len(lines) and lines[cursor].rstrip("\r\n"):
            positions.append(cursor)
            cursor += 1
        if cursor == start:
            raise TranslationError("empty SRT cue")
    if not positions:
        raise TranslationError("SRT contains no text")
    return positions


def native_translate_lines(backend: object, lines: Sequence[str],
                           source_language: str) -> Tuple[str, ...]:
    """Testable native backend adapter, exactly <=50 text lines per call."""
    if source_language not in ("ja", "en"):
        raise TranslationError("source language must be ja or en")
    translated = []
    for offset in range(0, len(lines), 50):
        batch = list(lines[offset:offset + 50])
        try:
            result = backend.translate_batch(batch, source_language, "zh")
        except Exception as exc:
            # Only the native line-count failure permits bounded subdivision.
            # Authentication, network, alignment and content-filter errors abort.
            if (type(exc).__module__ == "translation.llm_base"
                    and type(exc).__name__ == "LineCountMismatchError"
                    and len(batch) > 6):
                midpoint = len(batch) // 2
                translated.extend(native_translate_lines(backend, batch[:midpoint], source_language))
                translated.extend(native_translate_lines(backend, batch[midpoint:], source_language))
                continue
            raise TranslationError("native translation batch failed") from exc
        # Sublarr returns TranslationResult, not a raw list. Fail closed on
        # unsuccessful results before reading their translated_lines.
        if not isinstance(result, (list, tuple)):
            if (getattr(result, "success", None) is not True
                    or getattr(result, "error", None)):
                raise TranslationError("native translation result failed")
            result = getattr(result, "translated_lines", None)
        if (not isinstance(result, (list, tuple)) or len(result) != len(batch)
                or any(not isinstance(line, str) or not line.strip()
                       or any(c in line for c in ("\n", "\r", "\x00", "\u0085", "\u2028", "\u2029"))
                       for line in result)):
            raise TranslationError("translation must return one nonempty line per input")
        translated.extend(result)
    return tuple(translated)


def translate_and_publish(candidate: Candidate, episode_id: str, output_path: str,
                          prepare_source: Callable[[Candidate], bytes],
                          backend: object, notification_outbox=None,
                          notification_generation=None) -> Path:
    if notification_outbox is not None:
        from media_notifications import run_with_notification
        if not notification_generation:
            raise ValueError('NOTIFICATION_GENERATION_REQUIRED')
        return run_with_notification(
            lambda: translate_and_publish(candidate, episode_id, output_path, prepare_source, backend),
            notification_outbox, 'subtitle', candidate.source_path, notification_generation,
            lambda result: ('completed', '已发布中文外挂字幕：' + str(result)))
    """Publish complete standalone .zh.srt atomically, never overwrite anything.

    prepare_source may normalize source bytes but must not alter the source file.
    Text cue count, text line count, indices, timelines, separators and line endings
    remain intact. Source SHA-256 is checked after preparation and before publish.
    The output directory must exist. Only our temporary publication file is removed.
    """
    if (not _eligible(candidate, episode_id) or candidate.subtitle_type != "text"
            or _language(candidate) not in ("ja", "en")):
        raise TranslationError("ineligible translation source")
    output = Path(output_path)
    if not output.name.endswith(".zh.srt"):
        raise TranslationError("output must be an independent .zh.srt")
    if os.path.lexists(str(output)):
        raise ExistingChineseError("Chinese output already exists; not overwriting")
    source_hash = _digest(candidate.source_path)
    try:
        raw = prepare_source(candidate)
        if not isinstance(raw, bytes):
            raise TypeError("prepare_source must return UTF-8 SRT bytes")
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
    except Exception as exc:
        raise TranslationError("source preparation failed") from exc
    _check_source(candidate.source_path, source_hash)
    lines = text.splitlines(keepends=True)
    positions = _text_positions(lines)
    source_lines = [lines[i].rstrip("\r\n") for i in positions]
    translated = native_translate_lines(backend, source_lines, _language(candidate))
    for index, replacement in zip(positions, translated):
        original = lines[index]
        ending = original[len(original.rstrip("\r\n")):]
        lines[index] = replacement + ending
    rendered = (("\ufeff" if bom else "") + "".join(lines)).encode("utf-8")
    # Hard link is an atomic no-replace publish on the same filesystem. There is
    # deliberately no rename fallback, because rename could replace a concurrent
    # Chinese subtitle. Unsupported filesystems fail closed.
    with tempfile.NamedTemporaryFile(prefix=".subtitle-fallback-", suffix=".tmp",
                                     dir=str(output.parent)) as temporary:
        temporary.write(rendered)
        temporary.flush()
        # The published link inherits this inode mode; 0600 hides it from Emby.
        os.fchmod(temporary.fileno(), 0o644)
        os.fsync(temporary.fileno())
        _check_source(candidate.source_path, source_hash)
        try:
            os.link(temporary.name, str(output))
        except FileExistsError as exc:
            raise ExistingChineseError("Chinese output appeared; not overwriting") from exc
    return output

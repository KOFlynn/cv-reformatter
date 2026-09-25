"""The response cache: one labelling result per (labeller identity, source
document), so a second run over unchanged inputs makes no LLM call.

The key is the spec's ``(model, prompt hash, schema hash, source sha256)``
with ``model`` widened to the whole labeller configuration: a change to
effort, temperature or any other sampling knob counts as a model change
under the eval-run rule, so it must miss the cache too. A labelling failure
is cached like any other answer (it is what the model said); a provider
error is not an answer and is never cached.

The directory is gitignored (``.cache/``) and must stay out of the runtime
image: it holds LLM answers quoting the golden set, and committing LLM
responses or the eval cache is out of scope for the repo.
"""

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel

from cvr.golden.generate import GENERATED_DIR
from cvr.models import (
    Labelling,
    LabellingFailure,
    LabellingResult,
    LabelRun,
    SourceBlock,
)
from cvr.pipeline import Labeller

__all__ = [
    "CACHE_DIR",
    "CacheStats",
    "CachedLabeller",
    "LabellerIdentity",
    "ResponseCache",
    "cache_key",
]

# The repository root's .cache/, beside fixtures/ (gitignored).
CACHE_DIR = GENERATED_DIR.parents[1] / ".cache" / "eval-responses"


@dataclass(frozen=True)
class LabellerIdentity:
    """What a labelling answer depends on besides the document: the
    configuration as plain values, and the prompt and schema versions with
    the hashes they stand for. Printed in the report; hashed into the key."""

    config: Mapping[str, object]
    prompt_version: str
    prompt_hash: str
    schema_version: str
    schema_hash: str


def cache_key(identity: LabellerIdentity, source: bytes) -> str:
    """The sha256 of the configuration, prompt hash, schema hash and the
    source document's sha256, as canonical JSON."""
    parts = {
        "config": dict(identity.config),
        "prompt_hash": identity.prompt_hash,
        "schema_hash": identity.schema_hash,
        "source_sha256": hashlib.sha256(source).hexdigest(),
    }
    text = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Entry(BaseModel):
    """One cached answer, with the key's parts beside it for a reader."""

    kind: Literal["labelling", "failure"]
    labelling: Labelling | None = None
    failure: LabellingFailure | None = None
    label_run: LabelRun | None = None


@dataclass
class ResponseCache:
    """A directory of ``<key>.json`` files, one per cached answer."""

    directory: Path = CACHE_DIR

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> tuple[LabellingResult, LabelRun | None] | None:
        path = self._path(key)
        if not path.exists():
            return None
        entry = _Entry.model_validate_json(path.read_text(encoding="utf-8"))
        result = entry.labelling if entry.kind == "labelling" else entry.failure
        assert result is not None, path
        return result, entry.label_run

    def put(
        self, key: str, result: LabellingResult, label_run: LabelRun | None
    ) -> None:
        if isinstance(result, Labelling):
            entry = _Entry(kind="labelling", labelling=result, label_run=label_run)
        else:
            entry = _Entry(kind="failure", failure=result, label_run=label_run)
        self.directory.mkdir(parents=True, exist_ok=True)
        # Written whole then renamed, so a run killed mid-write never leaves a
        # truncated answer for the next run to replay.
        path = self._path(key)
        partial = path.with_suffix(".partial")
        partial.write_text(entry.model_dump_json(indent=1), encoding="utf-8")
        partial.replace(path)


@dataclass
class CacheStats:
    """Hits and live calls over one eval run, safe across worker threads."""

    hits: int = 0
    live_calls: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def hit(self) -> None:
        with self._lock:
            self.hits += 1

    def live(self) -> None:
        with self._lock:
            self.live_calls += 1


@dataclass
class CachedLabeller:
    """One document's labeller seen through the cache: a hit replays the
    stored answer and its ``LabelRun``; a miss makes the live labeller (built
    only then, so a fully cached run needs no API key) and stores what it
    answered. ``read=False`` (``--no-cache``) skips the lookup but still
    stores the fresh answer, so the next cached run replays the latest one.

    Like ``RealLabeller``, it records the call's ``LabelRun`` on
    ``last_run`` for the pipeline to read.
    """

    live: Callable[[], Labeller]
    cache: ResponseCache
    key: str
    stats: CacheStats
    read: bool = True
    last_run: LabelRun | None = None
    hit: bool = False

    def __call__(self, blocks: Sequence[SourceBlock]) -> LabellingResult:
        self.last_run = None
        if self.read and (cached := self.cache.get(self.key)) is not None:
            self.hit = True
            self.stats.hit()
            result, self.last_run = cached
            return result
        labeller = self.live()
        self.stats.live()
        result = labeller(blocks)
        last_run = getattr(labeller, "last_run", None)
        self.last_run = last_run if isinstance(last_run, LabelRun) else None
        self.cache.put(self.key, result, self.last_run)
        return result

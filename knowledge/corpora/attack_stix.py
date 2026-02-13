"""Production-grade ATT&CK Enterprise ingestion via STIX/TAXII 2.0.

Fetches from MITRE's official TAXII endpoint, parses STIX objects into
the internal KnowledgeDocument schema, and supports incremental updates.

CLI usage:
    python -m knowledge.corpora.attack_stix --out knowledge/corpora/cache/attack.jsonl
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from knowledge.corpora.loaders import KnowledgeDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TAXII_BASE = "https://cti-taxii.mitre.org/stix/collections"
ENTERPRISE_COLLECTION_ID = "95ecc380-afe9-11e4-9b6c-751b66dd541e"
ENTERPRISE_OBJECTS_URL = (
    f"{TAXII_BASE}/{ENTERPRISE_COLLECTION_ID}/objects/"
)

TAXII_ACCEPT = "application/stix+json;version=2.0"

# Tactic shortname -> display name mapping
TACTIC_DISPLAY_NAMES = {
    "reconnaissance": "Reconnaissance",
    "resource-development": "Resource Development",
    "initial-access": "Initial Access",
    "execution": "Execution",
    "persistence": "Persistence",
    "privilege-escalation": "Privilege Escalation",
    "defense-evasion": "Defense Evasion",
    "credential-access": "Credential Access",
    "discovery": "Discovery",
    "lateral-movement": "Lateral Movement",
    "collection": "Collection",
    "command-and-control": "Command and Control",
    "exfiltration": "Exfiltration",
    "impact": "Impact",
}

DEFAULT_CACHE_DIR = Path("knowledge/corpora/cache")
STATE_FILENAME = "attack_ingest_state.json"


# ---------------------------------------------------------------------------
# TAXII 2.0 Client
# ---------------------------------------------------------------------------

class ATTACKSTIXClient:
    """Fetches STIX bundles from MITRE's TAXII 2.0 server."""

    def __init__(
        self,
        *,
        base_url: str = ENTERPRISE_OBJECTS_URL,
        timeout: int = 120,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        cache_dir: Optional[Path] = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": TAXII_ACCEPT,
            "User-Agent": "CyberSentinel/1.0 ATT&CK-Ingest",
        })

    # -- public API ---------------------------------------------------------

    def fetch_enterprise_bundle(self) -> Dict[str, Any]:
        """Fetch the full Enterprise ATT&CK STIX bundle.

        Returns the parsed JSON bundle dict.  Uses retry logic with
        exponential backoff for transient failures.
        """
        logger.info("Fetching Enterprise ATT&CK STIX bundle from TAXII server…")
        all_objects: List[Dict[str, Any]] = []
        url: Optional[str] = self.base_url

        while url:
            data = self._fetch_with_retry(url)
            objects = data.get("objects", [])
            all_objects.extend(objects)
            logger.info(f"  Fetched page with {len(objects)} objects (total: {len(all_objects)})")
            # TAXII 2.0 pagination via "next" in response
            url = data.get("next")

        bundle = {
            "type": "bundle",
            "id": data.get("id", f"bundle--cybersentinel-ingest-{int(time.time())}"),
            "spec_version": data.get("spec_version", "2.0"),
            "objects": all_objects,
        }
        logger.info(f"Fetched bundle with {len(all_objects)} total STIX objects")
        return bundle

    def fetch_or_load_cached(self, cache_path: Optional[Path] = None) -> Dict[str, Any]:
        """Return cached bundle if available, otherwise fetch and cache."""
        cache_file = cache_path or (self.cache_dir / "enterprise_attack_bundle.json")

        if cache_file.exists():
            logger.info(f"Loading cached STIX bundle from {cache_file}")
            with open(cache_file, "r") as f:
                return json.load(f)

        bundle = self.fetch_enterprise_bundle()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(bundle, f)
        logger.info(f"Cached STIX bundle to {cache_file}")
        return bundle

    # -- internal -----------------------------------------------------------

    def _fetch_with_retry(self, url: str) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = self.backoff_factor ** attempt
                    logger.warning(
                        f"TAXII fetch attempt {attempt}/{self.max_retries} failed: {exc}. "
                        f"Retrying in {wait:.1f}s…"
                    )
                    time.sleep(wait)
        raise RuntimeError(
            f"Failed to fetch STIX bundle after {self.max_retries} attempts: {last_exc}"
        ) from last_exc


# ---------------------------------------------------------------------------
# STIX Parser
# ---------------------------------------------------------------------------

class STIXParser:
    """Parses STIX 2.0 objects into CyberSentinel KnowledgeDocument instances."""

    @staticmethod
    def parse_bundle(
        bundle: Dict[str, Any],
        *,
        include_tactics: bool = True,
        include_mitigations: bool = True,
        include_groups: bool = True,
    ) -> "STIXParseResult":
        """Parse a STIX bundle into internal documents and relationship data.

        Returns a STIXParseResult with technique docs plus optional
        tactic / mitigation / group docs and relationship tuples.
        """
        objects = bundle.get("objects", [])
        objects_by_id: Dict[str, Dict[str, Any]] = {
            obj["id"]: obj for obj in objects if "id" in obj
        }

        techniques: List[KnowledgeDocument] = []
        tactics: List[KnowledgeDocument] = []
        mitigations: List[KnowledgeDocument] = []
        groups: List[KnowledgeDocument] = []
        tactic_memberships: List[Tuple[str, str]] = []  # (technique_ext_id, tactic_name)
        data_source_map: Dict[str, List[str]] = {}  # technique_ext_id -> [data_sources]

        for obj in objects:
            obj_type = obj.get("type", "")

            # Skip revoked / deprecated objects
            if obj.get("revoked", False) or obj.get("x_mitre_deprecated", False):
                continue

            if obj_type == "attack-pattern":
                doc = STIXParser._parse_attack_pattern(obj)
                if doc:
                    techniques.append(doc)
                    ext_id = doc.metadata.get("attack_id", "")
                    # Collect tactic memberships
                    for phase in obj.get("kill_chain_phases", []):
                        if phase.get("kill_chain_name") == "mitre-attack":
                            tactic_name = TACTIC_DISPLAY_NAMES.get(
                                phase["phase_name"], phase["phase_name"].replace("-", " ").title()
                            )
                            tactic_memberships.append((ext_id, tactic_name))
                    # Collect data sources
                    ds = obj.get("x_mitre_data_sources", [])
                    if ds:
                        data_source_map[ext_id] = ds

            elif obj_type == "x-mitre-tactic" and include_tactics:
                doc = STIXParser._parse_tactic(obj)
                if doc:
                    tactics.append(doc)

            elif obj_type == "course-of-action" and include_mitigations:
                doc = STIXParser._parse_mitigation(obj)
                if doc:
                    mitigations.append(doc)

            elif obj_type == "intrusion-set" and include_groups:
                doc = STIXParser._parse_group(obj)
                if doc:
                    groups.append(doc)

        logger.info(
            f"Parsed STIX bundle: {len(techniques)} techniques, "
            f"{len(tactics)} tactics, {len(mitigations)} mitigations, "
            f"{len(groups)} groups, {len(tactic_memberships)} tactic memberships"
        )

        return STIXParseResult(
            techniques=techniques,
            tactics=tactics,
            mitigations=mitigations,
            groups=groups,
            tactic_memberships=tactic_memberships,
            data_source_map=data_source_map,
        )

    # -- individual object parsers ------------------------------------------

    @staticmethod
    def _parse_attack_pattern(obj: Dict[str, Any]) -> Optional[KnowledgeDocument]:
        ext_id, url = STIXParser._extract_mitre_external(obj)
        if not ext_id:
            return None

        stix_id = obj["id"]
        name = obj.get("name", "")
        description = obj.get("description", "")
        platforms = obj.get("x_mitre_platforms", [])
        data_sources = obj.get("x_mitre_data_sources", [])
        is_sub = obj.get("x_mitre_is_subtechnique", False)
        detection = obj.get("x_mitre_detection", "")

        # Gather tactics from kill chain phases
        tactics = []
        for phase in obj.get("kill_chain_phases", []):
            if phase.get("kill_chain_name") == "mitre-attack":
                display = TACTIC_DISPLAY_NAMES.get(
                    phase["phase_name"], phase["phase_name"].replace("-", " ").title()
                )
                tactics.append(display)

        # Build content blob (matches format expected by ATTACKChunker)
        content_parts = [
            f"Technique: {name}",
            f"ID: {ext_id}",
            f"Tactic: {', '.join(tactics) if tactics else 'Unknown'}",
            f"Platforms: {', '.join(platforms)}",
            "",
            "Description:",
            description,
        ]
        if data_sources:
            content_parts += ["", "Data Sources:", ", ".join(data_sources)]
        if detection:
            content_parts += ["", "Detection:", detection]

        content = "\n".join(content_parts)

        # Stable ID: external_id + STIX id
        stable_id = f"{ext_id}--{stix_id}"

        return KnowledgeDocument(
            id=stable_id,
            title=name,
            content=content,
            doc_type="attack_technique",
            source="mitre_attack",
            url=url or f"https://attack.mitre.org/techniques/{ext_id.replace('.', '/')}/",
            metadata={
                "attack_id": ext_id,
                "stix_id": stix_id,
                "tactic": tactics[0] if tactics else "Unknown",
                "tactics": tactics,
                "platforms": platforms,
                "data_sources": data_sources,
                "is_subtechnique": is_sub,
                "mitre_version": obj.get("x_mitre_version", ""),
                "created": obj.get("created", ""),
                "modified": obj.get("modified", ""),
            },
        )

    @staticmethod
    def _parse_tactic(obj: Dict[str, Any]) -> Optional[KnowledgeDocument]:
        ext_id, url = STIXParser._extract_mitre_external(obj)
        if not ext_id:
            return None
        stix_id = obj["id"]
        name = obj.get("name", "")
        description = obj.get("description", "")
        shortname = obj.get("x_mitre_shortname", "")
        content = f"Tactic: {name}\nID: {ext_id}\nShortname: {shortname}\n\nDescription:\n{description}"
        return KnowledgeDocument(
            id=f"{ext_id}--{stix_id}",
            title=name,
            content=content,
            doc_type="attack_tactic",
            source="mitre_attack",
            url=url or f"https://attack.mitre.org/tactics/{ext_id}/",
            metadata={
                "tactic_id": ext_id,
                "stix_id": stix_id,
                "shortname": shortname,
            },
        )

    @staticmethod
    def _parse_mitigation(obj: Dict[str, Any]) -> Optional[KnowledgeDocument]:
        ext_id, url = STIXParser._extract_mitre_external(obj)
        if not ext_id:
            return None
        stix_id = obj["id"]
        name = obj.get("name", "")
        description = obj.get("description", "")
        content = f"Mitigation: {name}\nID: {ext_id}\n\nDescription:\n{description}"
        return KnowledgeDocument(
            id=f"{ext_id}--{stix_id}",
            title=name,
            content=content,
            doc_type="attack_mitigation",
            source="mitre_attack",
            url=url or "",
            metadata={
                "mitigation_id": ext_id,
                "stix_id": stix_id,
            },
        )

    @staticmethod
    def _parse_group(obj: Dict[str, Any]) -> Optional[KnowledgeDocument]:
        ext_id, url = STIXParser._extract_mitre_external(obj)
        if not ext_id:
            return None
        stix_id = obj["id"]
        name = obj.get("name", "")
        description = obj.get("description", "")
        aliases = obj.get("aliases", [])
        content = (
            f"Threat Group: {name}\nID: {ext_id}\n"
            f"Aliases: {', '.join(aliases)}\n\nDescription:\n{description}"
        )
        return KnowledgeDocument(
            id=f"{ext_id}--{stix_id}",
            title=name,
            content=content,
            doc_type="attack_group",
            source="mitre_attack",
            url=url or "",
            metadata={
                "group_id": ext_id,
                "stix_id": stix_id,
                "aliases": aliases,
            },
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _extract_mitre_external(obj: Dict[str, Any]) -> Tuple[str, str]:
        """Return (external_id, url) from MITRE external references."""
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return ref.get("external_id", ""), ref.get("url", "")
        return "", ""


# ---------------------------------------------------------------------------
# Parse result container
# ---------------------------------------------------------------------------

class STIXParseResult:
    """Container for parsed STIX bundle data."""

    def __init__(
        self,
        techniques: List[KnowledgeDocument],
        tactics: List[KnowledgeDocument],
        mitigations: List[KnowledgeDocument],
        groups: List[KnowledgeDocument],
        tactic_memberships: List[Tuple[str, str]],
        data_source_map: Dict[str, List[str]],
    ):
        self.techniques = techniques
        self.tactics = tactics
        self.mitigations = mitigations
        self.groups = groups
        self.tactic_memberships = tactic_memberships
        self.data_source_map = data_source_map

    @property
    def all_documents(self) -> List[KnowledgeDocument]:
        return self.techniques + self.tactics + self.mitigations + self.groups

    @property
    def technique_count(self) -> int:
        return len(self.techniques)


# ---------------------------------------------------------------------------
# Incremental update tracker
# ---------------------------------------------------------------------------

class IncrementalTracker:
    """Tracks content hashes for incremental ingest (upsert only changed docs)."""

    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path or (DEFAULT_CACHE_DIR / STATE_FILENAME)
        self._state: Dict[str, Any] = self._load_state()

    # -- public API ---------------------------------------------------------

    def compute_diff(
        self, documents: List[KnowledgeDocument]
    ) -> Tuple[List[KnowledgeDocument], List[KnowledgeDocument], List[str]]:
        """Compare documents against stored state.

        Returns (new_or_changed, unchanged, removed_ids).
        """
        old_hashes: Dict[str, str] = self._state.get("object_hashes", {})
        new_hashes: Dict[str, str] = {}
        new_or_changed: List[KnowledgeDocument] = []
        unchanged: List[KnowledgeDocument] = []

        for doc in documents:
            h = self._hash_document(doc)
            new_hashes[doc.id] = h
            if doc.id not in old_hashes or old_hashes[doc.id] != h:
                new_or_changed.append(doc)
            else:
                unchanged.append(doc)

        removed_ids = [did for did in old_hashes if did not in new_hashes]

        logger.info(
            f"Incremental diff: {len(new_or_changed)} new/changed, "
            f"{len(unchanged)} unchanged, {len(removed_ids)} removed"
        )
        return new_or_changed, unchanged, removed_ids

    def save_state(self, documents: List[KnowledgeDocument]) -> None:
        """Persist the current document hash map."""
        hashes = {doc.id: self._hash_document(doc) for doc in documents}
        self._state = {
            "last_ingest": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "document_count": len(documents),
            "object_hashes": hashes,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self._state, f, indent=2)
        logger.info(f"Saved ingest state ({len(hashes)} hashes) to {self.state_path}")

    def clear_state(self) -> None:
        if self.state_path.exists():
            self.state_path.unlink()
        self._state = {}

    @property
    def last_ingest(self) -> Optional[str]:
        return self._state.get("last_ingest")

    @property
    def stored_count(self) -> int:
        return len(self._state.get("object_hashes", {}))

    # -- internal -----------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            with open(self.state_path, "r") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _hash_document(doc: KnowledgeDocument) -> str:
        payload = f"{doc.id}|{doc.title}|{doc.content}|{json.dumps(doc.metadata, sort_keys=True)}"
        return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class ATTACKIngestPipeline:
    """Orchestrates end-to-end ATT&CK STIX ingestion."""

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = None,
        offline_bundle_path: Optional[Path] = None,
        include_tactics: bool = True,
        include_mitigations: bool = True,
        include_groups: bool = True,
    ):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline_bundle_path = offline_bundle_path
        self.include_tactics = include_tactics
        self.include_mitigations = include_mitigations
        self.include_groups = include_groups
        self.client = ATTACKSTIXClient(cache_dir=self.cache_dir)
        self.tracker = IncrementalTracker(
            state_path=self.cache_dir / STATE_FILENAME
        )

    def run(
        self, *, force: bool = False
    ) -> Tuple[List[KnowledgeDocument], Dict[str, Any]]:
        """Execute the full ingestion pipeline.

        Args:
            force: If True, skip incremental diff and treat all docs as new.

        Returns:
            (documents_to_upsert, stats_dict)
        """
        # Step 1: Obtain STIX bundle
        bundle = self._load_bundle()

        # Step 2: Parse into KnowledgeDocuments
        parse_result = STIXParser.parse_bundle(
            bundle,
            include_tactics=self.include_tactics,
            include_mitigations=self.include_mitigations,
            include_groups=self.include_groups,
        )
        all_docs = parse_result.all_documents

        # Step 3: Incremental diff
        if force:
            upsert_docs = all_docs
            removed_ids: List[str] = []
            unchanged_count = 0
        else:
            upsert_docs, unchanged, removed_ids = self.tracker.compute_diff(all_docs)
            unchanged_count = len(unchanged)

        # Step 4: Save state
        self.tracker.save_state(all_docs)

        stats = {
            "total_stix_objects": len(bundle.get("objects", [])),
            "techniques_parsed": parse_result.technique_count,
            "tactics_parsed": len(parse_result.tactics),
            "mitigations_parsed": len(parse_result.mitigations),
            "groups_parsed": len(parse_result.groups),
            "tactic_memberships": len(parse_result.tactic_memberships),
            "docs_to_upsert": len(upsert_docs),
            "docs_unchanged": unchanged_count,
            "docs_removed": len(removed_ids),
            "removed_ids": removed_ids,
        }
        logger.info(f"Ingest pipeline completed: {stats}")
        return upsert_docs, stats

    def run_full(self, *, force: bool = False) -> Tuple[STIXParseResult, Dict[str, Any]]:
        """Execute pipeline and return full parse result (for graph sync)."""
        bundle = self._load_bundle()
        parse_result = STIXParser.parse_bundle(
            bundle,
            include_tactics=self.include_tactics,
            include_mitigations=self.include_mitigations,
            include_groups=self.include_groups,
        )
        all_docs = parse_result.all_documents
        if force:
            upsert_count = len(all_docs)
            removed_ids: List[str] = []
            unchanged_count = 0
        else:
            upsert, unchanged, removed_ids = self.tracker.compute_diff(all_docs)
            upsert_count = len(upsert)
            unchanged_count = len(unchanged)
        self.tracker.save_state(all_docs)
        stats = {
            "total_stix_objects": len(bundle.get("objects", [])),
            "techniques_parsed": parse_result.technique_count,
            "docs_to_upsert": upsert_count,
            "docs_unchanged": unchanged_count,
            "docs_removed": len(removed_ids),
        }
        return parse_result, stats

    def _load_bundle(self) -> Dict[str, Any]:
        if self.offline_bundle_path:
            logger.info(f"Loading offline STIX bundle from {self.offline_bundle_path}")
            with open(self.offline_bundle_path, "r") as f:
                return json.load(f)
        return self.client.fetch_or_load_cached()

    # -- JSONL export -------------------------------------------------------

    @staticmethod
    def export_jsonl(documents: List[KnowledgeDocument], output_path: Path) -> int:
        """Write documents to a JSONL file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(output_path, "w") as f:
            for doc in documents:
                record = {
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.content,
                    "doc_type": doc.doc_type,
                    "source": doc.source,
                    "url": doc.url,
                    "metadata": doc.metadata,
                }
                f.write(json.dumps(record) + "\n")
                count += 1
        logger.info(f"Exported {count} documents to {output_path}")
        return count

    @staticmethod
    def load_jsonl(input_path: Path) -> List[KnowledgeDocument]:
        """Load documents from a JSONL file."""
        docs: List[KnowledgeDocument] = []
        with open(input_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                docs.append(KnowledgeDocument(
                    id=record["id"],
                    title=record["title"],
                    content=record["content"],
                    doc_type=record["doc_type"],
                    source=record["source"],
                    url=record.get("url", ""),
                    metadata=record.get("metadata", {}),
                ))
        logger.info(f"Loaded {len(docs)} documents from {input_path}")
        return docs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ingest MITRE ATT&CK Enterprise data via STIX/TAXII"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_CACHE_DIR / "attack.jsonl",
        help="Output JSONL path (default: knowledge/corpora/cache/attack.jsonl)",
    )
    parser.add_argument(
        "--offline",
        type=Path,
        default=None,
        help="Path to a local STIX bundle JSON for offline mode",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full re-ingest (skip incremental diff)",
    )
    parser.add_argument(
        "--no-tactics",
        action="store_true",
        help="Skip parsing tactic objects",
    )
    parser.add_argument(
        "--no-mitigations",
        action="store_true",
        help="Skip parsing mitigation objects",
    )
    parser.add_argument(
        "--no-groups",
        action="store_true",
        help="Skip parsing group objects",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Cache directory",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    pipeline = ATTACKIngestPipeline(
        cache_dir=args.cache_dir,
        offline_bundle_path=args.offline,
        include_tactics=not args.no_tactics,
        include_mitigations=not args.no_mitigations,
        include_groups=not args.no_groups,
    )

    upsert_docs, stats = pipeline.run(force=args.force)

    # Export all parsed docs (not just upserts) so the JSONL is a complete snapshot
    all_docs = upsert_docs  # On first run or force, this is everything
    count = ATTACKIngestPipeline.export_jsonl(all_docs, args.out)

    print(f"\nATT&CK ingest complete:")
    print(f"  Techniques parsed: {stats['techniques_parsed']}")
    print(f"  Documents to upsert: {stats['docs_to_upsert']}")
    print(f"  Documents unchanged: {stats['docs_unchanged']}")
    print(f"  Documents removed: {stats['docs_removed']}")
    print(f"  JSONL written: {count} docs → {args.out}")


if __name__ == "__main__":
    main()

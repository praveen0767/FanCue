"""Command-line interface for FanCue knowledge base validation, chunking, ingestion, and evaluation."""

import argparse
import json
import sys
from typing import List, Optional

from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.retrieval import RetrievalQuery
from ingestion.knowledge.chunker import chunk_document
from ingestion.knowledge.embeddings import FastEmbedProvider
from ingestion.knowledge.evaluate import evaluate_retrieval
from ingestion.knowledge.ingest import run_ingestion
from ingestion.knowledge.loader import load_knowledge_corpus, load_sources_registry
from ingestion.knowledge.qdrant_store import DEV_COLLECTION_NAME, PROD_COLLECTION_NAME, QdrantStore
from ingestion.knowledge.retrieve import RetrievalService
from ingestion.knowledge.validator import validate_document_governance


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate all source documents and registry manifest."""
    print("=== FanCue Knowledge Base Validation ===")
    try:
        registry = load_sources_registry(args.sources_registry)
        print(f"[OK] Sources registry loaded: version {registry.get('version', 'unknown')} with {len(registry.get('sources', []))} sources.")
    except Exception as e:
        print(f"[ERROR] Failed to load sources registry: {e}")
        return 1

    docs = load_knowledge_corpus(args.corpus_dir, include_drafts=True)
    print(f"Discovered {len(docs)} documents ({sum(1 for d in docs if not d.is_draft)} approved, {sum(1 for d in docs if d.is_draft)} draft).")

    errors = 0
    for doc in docs:
        try:
            validate_document_governance(doc, sources_registry=registry)
            status_str = "DRAFT" if doc.is_draft else "APPROVED"
            print(f"  [VALID] [{status_str}] {doc.frontmatter.id} — '{doc.frontmatter.title}'")
        except Exception as e:
            errors += 1
            print(f"  [INVALID] {doc.filepath}: {e}")

    if errors > 0:
        print(f"\n[FAILED] {errors} validation error(s) found.")
        return 1

    print("\n[SUCCESS] All knowledge documents and registry entries passed validation.")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """Preview semantic chunking, deterministic IDs, token counts, and metadata."""
    print("=== FanCue Knowledge Chunking Preview ===")
    embedder = FastEmbedProvider()
    docs = load_knowledge_corpus(args.corpus_dir, include_drafts=args.include_drafts)

    total_chunks = 0
    for doc in docs:
        chunks = chunk_document(doc, embedder=embedder)
        total_chunks += len(chunks)
        print(f"\nDocument: {doc.frontmatter.id} ({doc.frontmatter.title})")
        print(f"  Source: {doc.frontmatter.source_name} | Revision: {doc.frontmatter.source_revision}")
        print(f"  Chunks: {len(chunks)}")
        for c in chunks:
            print(f"    - [{c.chunk_id}] (tokens: {c.token_count}) Point UUID: {c.point_id}")
            print(f"      Section: '{c.payload.section_title}'")
            preview_txt = c.payload.text[:80].replace("\n", " ")
            print(f"      Snippet: \"{preview_txt}...\"")

    print(f"\nTotal previewed: {len(docs)} documents segmented into {total_chunks} chunks.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Execute dry-run or apply ingestion."""
    is_dry_run = not args.apply
    print(f"=== FanCue Knowledge Ingestion (Target: '{args.collection}', DryRun={is_dry_run}) ===")

    report = run_ingestion(
        target_collection=args.collection,
        dry_run=is_dry_run,
        allow_draft=args.allow_draft,
        corpus_base_dir=args.corpus_dir,
        sources_registry_path=args.sources_registry,
    )

    print(f"Status: {report.execution_status}")
    print(f"Documents Discovered: {report.documents_discovered}")
    print(f"Documents Accepted: {report.documents_accepted}")
    print(f"Documents Rejected: {report.documents_rejected}")
    if report.rejection_reasons:
        for doc_id, reason in report.rejection_reasons.items():
            print(f"  - Rejected {doc_id}: {reason}")
    print(f"Chunks Generated: {report.chunks_generated}")
    if not is_dry_run:
        print(f"Chunks Embedded: {report.chunks_embedded}")
        print(f"Points Upserted: {report.points_upserted}")
        print(f"Total Points in Collection Now: {report.points_total_after}")

    if report.execution_status in ("dry_run_success", "applied_success"):
        return 0
    return 1


def cmd_retrieve(args: argparse.Namespace) -> int:
    """Run an ad-hoc query against the retrieval service."""
    print(f"=== FanCue Knowledge Retrieval (Collection: '{args.collection}') ===")
    store = QdrantStore()
    service = RetrievalService(
        collection_name=args.collection,
        store=store,
        allow_draft=args.allow_draft,
    )

    query = RetrievalQuery(
        query_text=args.query,
        sport=SportType(args.sport),
        language=LanguageCode(args.language),
        limit=args.limit,
    )

    result = service.retrieve(query)
    print(f"Query: \"{args.query}\"")
    print(f"Status: {result.status.value}")
    if result.error_detail:
        print(f"Error Detail: {result.error_detail}")

    print(f"Retrieved Passages: {len(result.passages)}")
    for i, p in enumerate(result.passages, start=1):
        print(f"\n[{i}] Score: {p.score:.4f} | Doc: {p.doc_id} | Topic: {p.topic}")
        print(f"    Source: {p.source_name} ({p.source_url})")
        print(f"    Content: {p.content}")

    return 0 if result.status.value == "success" else 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Run the fixed evaluation suite and report metrics."""
    print(f"=== FanCue Retrieval Evaluation (Collection: '{args.collection}') ===")
    store = QdrantStore()
    service = RetrievalService(
        collection_name=args.collection,
        store=store,
        allow_draft=args.allow_draft,
    )

    metrics = evaluate_retrieval(service, eval_queries_path=args.eval_file)
    print("\n--- Evaluation Metrics ---")
    print(f"Total Queries: {metrics['total_queries']} ({metrics['in_scope_queries']} in-scope, {metrics['negative_queries']} negative)")
    print(f"HitRate@3: {metrics['hit_rate_at_3'] * 100:.2f}% (Target: >= 80.0%)")
    print(f"MRR@5: {metrics['mrr_at_5']:.4f}")
    print(f"Wrong Sport Leakage: {metrics['wrong_sport_leakage']} (Must be 0)")
    print(f"Wrong Language Leakage: {metrics['wrong_language_leakage']} (Must be 0)")
    print(f"Draft Leakage in Prod: {metrics['draft_leakage_count']} (Must be 0)")
    print(f"Negative Queries Handled Cleanly: {metrics['negative_handled_cleanly']}/{metrics['negative_queries']}")
    print(f"Average Latency: {metrics['avg_latency_ms']:.2f} ms")
    print(f"Gate Passed: {'PASSED' if metrics['passed_gate'] else 'FAILED'}")

    if metrics.get("failed_queries"):
        print("\nFailed Queries:")
        for f in metrics["failed_queries"]:
            print(f"  - [{f['id']}] \"{f['query']}\"")
            print(f"    Expected: {f['expected']}")
            print(f"    Got top-3: {f['retrieved']}")

    return 0 if metrics["passed_gate"] else 1


def main() -> None:
    # Ensure stdout/stderr handles UTF-8 (multilingual Tamil text) on Windows
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="FanCue Knowledge Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate source documents and manifest")
    p_val.add_argument("--corpus-dir", default="ingestion/knowledge")
    p_val.add_argument("--sources-registry", default="ingestion/knowledge/sources.yml")

    # preview
    p_prev = subparsers.add_parser("preview", help="Preview chunks and tokens")
    p_prev.add_argument("--corpus-dir", default="ingestion/knowledge")
    p_prev.add_argument("--include-drafts", action="store_true")

    # ingest
    p_ing = subparsers.add_parser("ingest", help="Ingest knowledge corpus")
    p_ing.add_argument("--apply", action="store_true", help="Apply writes to Qdrant (default is dry-run)")
    p_ing.add_argument("--collection", default=DEV_COLLECTION_NAME, help="Target Qdrant collection")
    p_ing.add_argument("--allow-draft", action="store_true", help="Allow draft documents into development collection")
    p_ing.add_argument("--corpus-dir", default="ingestion/knowledge")
    p_ing.add_argument("--sources-registry", default="ingestion/knowledge/sources.yml")

    # retrieve
    p_ret = subparsers.add_parser("retrieve", help="Query knowledge base")
    p_ret.add_argument("query", help="Search query string")
    p_ret.add_argument("--collection", default=DEV_COLLECTION_NAME)
    p_ret.add_argument("--sport", default="cricket")
    p_ret.add_argument("--language", default="en")
    p_ret.add_argument("--limit", type=int, default=3)
    p_ret.add_argument("--allow-draft", action="store_true")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Run retrieval evaluation suite")
    p_eval.add_argument("--collection", default=DEV_COLLECTION_NAME)
    p_eval.add_argument("--eval-file", default="ingestion/knowledge/evaluation/cricket_eval_queries.json")
    p_eval.add_argument("--allow-draft", action="store_true")

    args = parser.parse_args()

    if args.command == "validate":
        sys.exit(cmd_validate(args))
    elif args.command == "preview":
        sys.exit(cmd_preview(args))
    elif args.command == "ingest":
        sys.exit(cmd_ingest(args))
    elif args.command == "retrieve":
        sys.exit(cmd_retrieve(args))
    elif args.command == "evaluate":
        sys.exit(cmd_evaluate(args))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

from config import load_config
from pipeline.fetch_stage import fetch_papers, save_papers_cache, load_papers_cache
from pipeline.filter_stage import filter_papers
from pipeline.llm_client import create_llm_client
from pipeline.ranking_stage import rank_papers
from pipeline.summary_stage import select_top_papers, generate_summaries
from pipeline.report_stage import generate_json_report, generate_markdown_report
from pipeline.slack_notifier import notify_slack
from pipeline.logger import setup_logger, ErrorTracker

def run_pipeline(target_date: date, config, skip_cache: bool = False):
    """Run the complete daily papers pipeline."""
    # Create directories first
    cache_dir = Path(config.output.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    logger = setup_logger(log_file=f"logs/pipeline_{target_date}.log")
    error_tracker = ErrorTracker()
    
    logger.info(f"{'='*60}")
    logger.info(f"Daily Papers Pipeline - {target_date}")
    logger.info(f"{'='*60}")
    
    # Stage 1: Fetch
    fetch_cache = cache_dir / f"fetch_{target_date}.json"
    try:
        if not skip_cache and fetch_cache.exists():
            logger.info("[1/6] Fetch: Loading from cache...")
            papers = load_papers_cache(str(fetch_cache))
            logger.info(f"  ✓ Loaded {len(papers)} papers from cache")
        else:
            logger.info("[1/6] Fetch: Fetching papers from sources...")
            start = time.time()
            papers = fetch_papers(target_date, config)
            elapsed = time.time() - start
            save_papers_cache(papers, str(fetch_cache))
            logger.info(f"  ✓ Fetched {len(papers)} papers in {elapsed:.1f}s")
    except Exception as e:
        error_tracker.add_error("fetch", e)
        logger.error(f"  ✗ Fetch failed: {e}")
        raise
    
    if not papers:
        logger.warning("No papers found. Exiting.")
        return
    
    # Stage 2: Filter
    filter_cache = cache_dir / f"filtered_{target_date}.json"
    try:
        if not skip_cache and filter_cache.exists():
            logger.info("[2/6] Filter: Loading from cache...")
            filtered = load_papers_cache(str(filter_cache))
            logger.info(f"  ✓ Loaded {len(filtered)} papers from cache")
        else:
            logger.info("[2/6] Filter: Applying keyword filters...")
            start = time.time()
            filtered = filter_papers(papers, config)
            elapsed = time.time() - start
            save_papers_cache(filtered, str(filter_cache))
            logger.info(f"  ✓ Filtered to {len(filtered)} papers in {elapsed:.1f}s")
    except Exception as e:
        error_tracker.add_error("filter", e)
        logger.error(f"  ✗ Filter failed: {e}")
        raise
    
    if not filtered:
        logger.warning("No papers passed filters. Exiting.")
        return
    
    # Stage 3: Rank
    rank_cache = cache_dir / f"ranked_{target_date}.json"
    try:
        if not skip_cache and rank_cache.exists():
            logger.info("[3/6] Rank: Loading from cache...")
            ranked = load_papers_cache(str(rank_cache))
            logger.info(f"  ✓ Loaded {len(ranked)} papers from cache")
        else:
            logger.info("[3/6] Rank: Scoring papers with LLM...")
            start = time.time()
            client = create_llm_client(config)
            ranked = rank_papers(filtered, config, client)
            elapsed = time.time() - start
            save_papers_cache(ranked, str(rank_cache))
            logger.info(f"  ✓ Ranked {len(ranked)} papers in {elapsed:.1f}s")
            
            # Log score distribution
            scores = [p.relevance_score or 0 for p in ranked]
            if scores:
                logger.info(f"  Score range: {min(scores):.1f} - {max(scores):.1f}")
    except Exception as e:
        error_tracker.add_error("rank", e)
        logger.error(f"  ✗ Rank failed: {e}")
        raise
    
    # Stage 4: Summarize
    summary_cache = cache_dir / f"summarized_{target_date}.json"
    try:
        if not skip_cache and summary_cache.exists():
            logger.info("[4/6] Summarize: Loading from cache...")
            summarized = load_papers_cache(str(summary_cache))
            logger.info(f"  ✓ Loaded {len(summarized)} papers from cache")
        else:
            logger.info("[4/6] Summarize: Selecting top papers and generating summaries...")
            start = time.time()
            top_papers = select_top_papers(ranked, config)
            logger.info(f"  Selected {len(top_papers)} papers (top {config.output.top_n} OR score >= {config.output.score_threshold})")
            client = create_llm_client(config)
            summarized = generate_summaries(top_papers, client)
            elapsed = time.time() - start
            save_papers_cache(summarized, str(summary_cache))
            logger.info(f"  ✓ Generated summaries for {len(summarized)} papers in {elapsed:.1f}s")
    except Exception as e:
        error_tracker.add_error("summarize", e)
        logger.error(f"  ✗ Summarize failed: {e}")
        raise
    
    # Stage 5: Report
    try:
        logger.info("[5/6] Report: Generating output files...")
        start = time.time()
        reports_dir = Path(config.output.reports_dir)
        json_path = reports_dir / f"{target_date}.json"
        md_path = reports_dir / f"{target_date}.md"
        
        generate_json_report(summarized, target_date, str(json_path))
        generate_markdown_report(summarized, target_date, str(md_path))
        elapsed = time.time() - start
        logger.info(f"  ✓ Generated reports in {elapsed:.1f}s")
        logger.info(f"    - JSON: {json_path}")
        logger.info(f"    - Markdown: {md_path}")
    except Exception as e:
        error_tracker.add_error("report", e)
        logger.error(f"  ✗ Report failed: {e}")
        raise
    
    # Stage 6: Slack Notification (optional)
    if config.notifications and config.notifications.slack.enabled:
        try:
            logger.info("[6/6] Notify: Posting to Slack...")
            start = time.time()
            slack_stats = notify_slack(summarized, target_date, config)
            elapsed = time.time() - start
            
            if slack_stats["posted"] > 0:
                logger.info(f"  ✓ Posted {slack_stats['posted']} papers to Slack in {elapsed:.1f}s")
            if slack_stats["failed"] > 0:
                logger.warning(f"  ⚠ Failed to post {slack_stats['failed']} papers")
            if slack_stats["skipped"] > 0:
                logger.info(f"  ℹ Skipped {slack_stats['skipped']} papers (below min_score)")
        except Exception as e:
            error_tracker.add_error("slack", e)
            logger.error(f"  ✗ Slack notification failed: {e}")
            # Don't raise - Slack failures shouldn't break the pipeline
    
    logger.info(f"{'='*60}")
    logger.info(f"Pipeline complete! Found {len(summarized)} relevant papers.")
    logger.info(f"{'='*60}")
    
    if error_tracker.has_errors():
        logger.error(error_tracker.get_summary())

def main():
    parser = argparse.ArgumentParser(description="Daily academic paper review pipeline")
    parser.add_argument(
        "--date",
        type=str,
        help="Date to process (YYYY-MM-DD). Default: yesterday",
    )
    parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Force re-run all stages, ignoring cache",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config file",
    )
    
    args = parser.parse_args()
    
    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = date.today() - timedelta(days=1)
    
    config = load_config(args.config)
    
    try:
        run_pipeline(target_date, config, args.skip_cache)
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    main()

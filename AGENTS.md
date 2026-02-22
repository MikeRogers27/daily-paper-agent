# AGENTS.md - Daily Paper Agent Architecture

## Project Overview

The Daily Paper Agent is an automated pipeline for discovering, filtering, and ranking academic papers from arXiv and HuggingFace based on research interests. It uses LLM-powered analysis to score papers and generate summaries, producing daily reports in JSON and Markdown formats.

## Architecture

### Pipeline Flow
```
daily_papers.py (orchestrator)
    ↓
[1] fetch_stage → cache/fetch_YYYY-MM-DD.json
    ↓
[2] filter_stage → cache/filtered_YYYY-MM-DD.json
    ↓
[3] llm_ranking_stage → cache/ranked_YYYY-MM-DD.json
    ↓
[4] summary_stage → cache/summarized_YYYY-MM-DD.json
    ↓
[5] report_stage → reports/YYYY-MM-DD.{json,md}
```

### Core Components

#### 1. Data Model (`tools/models.py`)
- **Paper**: Core dataclass representing an academic paper
  - Fields: id, title, authors, abstract, source, url, published_date, tags, relevance_score, summary
  - Used throughout the pipeline to pass paper data between stages

#### 2. Data Sources (`tools/`)
- **arxiv_tool.py**: Fetches papers from arXiv API by date and category
- **hf_daily_tool.py**: Scrapes HuggingFace Daily Papers, fetches abstracts from detail pages
- Both return lists of Paper objects

#### 3. Pipeline Stages (`pipeline/`)

**fetch_stage.py**
- Aggregates papers from all enabled sources (arXiv, HuggingFace)
- Deduplicates by arXiv ID (prefers arXiv version with abstract)
- Saves raw papers to cache

**filter_stage.py**
- Applies keyword-based filtering on title and abstract
- Include/exclude keyword lists from config
- Reduces candidate set before expensive LLM calls

**ranking_stage.py**
- Contains `rank_papers()` function - the single source of truth for paper scoring
- Batches papers (5-10 per batch)
- Sends to LLM with relevance specification from `prompts/spec.md`
- Scores each paper on 1-5 scale
- Sorts by relevance score descending
- Used by both production pipeline and test scoring

**summary_stage.py**
- Selects top papers using hybrid logic: top N OR score ≥ threshold
- Generates 2-3 sentence summaries via LLM
- Updates Paper.summary field

**report_stage.py**
- Generates JSON report with all paper metadata
- Generates Markdown report grouped by score tier (5, 4, 3)
- Saves to `reports/` directory

#### 4. LLM Integration (`pipeline/`)

**llm_client.py**
- Abstract `LLMClient` base class with shared retry logic
- `create_llm_client(config)` factory function
- `parse_llm_response(response_text)` utility for extracting JSON from LLM responses
- Supports multiple providers via unified interface

**bedrock_client.py**
- AWS Bedrock (Claude) implementation
- Uses boto3 SDK for API calls
- Supports mock mode for testing

**gemini_client.py**
- Google Gemini implementation via gemini-cli
- Uses subprocess to call command-line tool
- Supports mock mode for testing

**slack_notifier.py**
- Slack webhook integration for notifications
- Posts highly relevant papers to Slack channels
- Configurable score threshold and rate limiting

#### 5. Configuration (`config.py`, `config.yaml`)
- Provider selection (bedrock/gemini)
- Source settings (arXiv categories, HuggingFace enabled)
- Filter keywords (include/exclude)
- LLM settings (model, batch size, retries)
- Output settings (top N, score threshold)

#### 6. Relevance Specification (`prompts/`)
- **spec.md**: Defines what papers are relevant to the research area
  - Used as system prompt for LLM ranking
  - Contains scoring rubric (1-5 scale)
  - Customizable per research domain
- **rank-papers.md**: Template prompt for batch paper ranking
- **refine-spec.md**: Prompt for LLM-assisted spec refinement
- **spec.example.md**: Example relevance specification

#### 7. Testing & Refinement Tools (`tools/`)
- **test_scoring.py**: Testing framework for relevance scoring
  - Loads test cases from YAML files
  - Converts test cases to Paper objects
  - Uses `rank_papers()` for consistent scoring with production
  - Calculates metrics (MAE, RMSE, accuracy)
  - Exports failures for spec refinement
- **refine_spec.py**: LLM-assisted spec refinement tool
  - Analyzes misclassified papers
  - Suggests improvements to relevance specification
  - Helps iteratively improve scoring accuracy

## Key Design Decisions

### 1. Stage-Based Pipeline
- Each stage is independent and cacheable
- Enables debugging and resume capability
- Clear separation of concerns

### 2. LLM Provider Abstraction
- Abstract base class allows multiple providers
- Factory pattern for instantiation
- Easy to add new providers (OpenAI, Anthropic Direct, etc.)

### 3. Hybrid Paper Selection
- Top N papers by score OR all papers ≥ threshold
- Ensures important papers aren't missed due to arbitrary cutoff
- Flexible based on daily paper volume

### 4. Deduplication Strategy
- Prefer arXiv versions (have full abstracts)
- HuggingFace papers without arXiv IDs are kept
- Prevents duplicate processing and reporting

### 5. Caching Strategy
- Save intermediate results after each stage
- Enables fast iteration during development
- Allows manual inspection of stage outputs
- `--skip-cache` flag to force re-run

## Data Flow

### Paper Object Lifecycle
1. **Created**: In fetch_stage from API/scraping
2. **Filtered**: In filter_stage based on keywords
3. **Scored**: In ranking_stage via LLM (relevance_score added)
4. **Selected**: In summary_stage based on hybrid logic
5. **Summarized**: In summary_stage via LLM (summary added)
6. **Reported**: In report_stage to JSON/Markdown

### Configuration Flow
1. Load from `config.yaml` via `load_config()`
2. Validate provider-specific settings
3. Pass to pipeline stages as needed
4. Factory uses config to create LLM client

## Extension Points

### Adding New Paper Sources
1. Create new tool in `tools/` (e.g., `semantic_scholar_tool.py`)
2. Return list of Paper objects
3. Update `fetch_stage.py` to call new tool
4. Add configuration in `config.yaml`

### Adding New LLM Providers
1. Create new client in `pipeline/` inheriting from `LLMClient`
2. Implement `_invoke_impl(prompt, system_prompt)`
3. Add provider config dataclass in `config.py`
4. Update factory in `llm_client.py`
5. Document in README

### Customizing Relevance Scoring
1. Edit `prompts/spec.md` with your research focus
2. Define scoring criteria (1-5 scale)
3. Include must-have and exclusion signals
4. Pipeline automatically uses updated spec

### Modifying Report Format
1. Edit `generate_markdown_report()` in `report_stage.py`
2. Edit `generate_json_report()` for structured output
3. Add new fields to Paper dataclass if needed

## Common Workflows

### Daily Usage
```bash
# Run for yesterday's papers (default)
python daily_papers.py

# Run for specific date
python daily_papers.py --date 2026-02-20

# Force re-run all stages
python daily_papers.py --skip-cache
```

### Switching LLM Providers
Edit `config.yaml`:
```yaml
llm:
  provider: gemini  # or "bedrock"
```

### Debugging Pipeline Issues
1. Check logs: `logs/pipeline_YYYY-MM-DD.log`
2. Inspect cache: `cache/fetch_YYYY-MM-DD.json`, etc.
3. Run with `--skip-cache` to force fresh run
4. Use `mock_mode: true` to test without API calls

### Customizing for New Research Area
1. Update `prompts/spec.md` with your focus
2. Update keywords in `config.yaml`
3. Adjust arXiv categories in `config.yaml`
4. Test with `--date` on known relevant papers

## File Organization

```
daily-paper-agent/
├── config.yaml              # Main configuration
├── config.py                # Configuration loader
├── daily_papers.py          # Main orchestrator
│
├── pipeline/                # Pipeline stages
│   ├── llm_client.py        # Abstract LLM interface + factory + parse_llm_response
│   ├── bedrock_client.py    # AWS Bedrock implementation
│   ├── gemini_client.py     # Gemini CLI implementation
│   ├── slack_notifier.py    # Slack webhook integration
│   ├── fetch_stage.py       # Fetch and deduplicate
│   ├── filter_stage.py      # Keyword filtering
│   ├── ranking_stage.py     # LLM ranking (rank_papers function)
│   ├── summary_stage.py     # Summary generation
│   ├── report_stage.py      # Report generation
│   └── logger.py            # Logging utilities
│
├── tools/                   # Data fetching and testing tools
│   ├── models.py            # Paper dataclass
│   ├── arxiv_tool.py        # ArXiv fetcher
│   ├── hf_daily_tool.py     # HuggingFace scraper
│   ├── test_scoring.py      # Test scoring framework
│   └── refine_spec.py       # Spec refinement tool
│
├── prompts/                 # LLM prompts
│   ├── spec.md              # Relevance specification
│   ├── rank-papers.md       # Batch ranking prompt template
│   ├── refine-spec.md       # Spec refinement prompt
│   └── spec.example.md      # Example spec
│
├── tests/                   # Test data
│   └── test-cases.example.yaml  # Example test cases
│
├── cache/                   # Intermediate results (gitignored)
├── reports/                 # Final outputs (gitignored)
└── logs/                    # Pipeline logs (gitignored)
```

## Dependencies

- **boto3**: AWS Bedrock API access
- **pyyaml**: Configuration parsing
- **requests**: HTTP requests for APIs
- **feedparser**: ArXiv RSS feed parsing
- **beautifulsoup4**: HTML parsing for HuggingFace

## Future Enhancements

1. **Additional Sources**: Semantic Scholar, OpenReview, CVPR/ICCV proceedings
2. **More LLM Providers**: OpenAI, Anthropic Direct API, local models
3. **Cost Tracking**: Monitor API usage and costs per provider
4. **Provider Fallback**: Automatic fallback if primary provider fails
5. **Parallel Processing**: Concurrent API calls for faster ranking
6. **Paper Clustering**: Group similar papers in reports
7. **Citation Analysis**: Track paper citations and impact
8. **Author Tracking**: Follow specific researchers
9. **Interactive UI**: Web interface for browsing and filtering

## Agent Context Notes

When working with this codebase:
- The pipeline is designed to be run daily, but can process any date
- All stages are idempotent and cacheable
- LLM calls are the most expensive operation (use mock mode for testing)
- The relevance specification is the key to good paper selection
- Configuration is centralized in config.yaml for easy customization
- The abstract LLM client makes it easy to switch providers or add new ones
- `rank_papers()` in ranking_stage.py is the single source of truth for scoring
- Test scoring uses the same `rank_papers()` function for consistency

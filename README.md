# Daily Paper Agent

An automated pipeline for discovering, filtering, and ranking academic papers from arXiv and HuggingFace based on your research interests.

## Features

- **Multi-source fetching**: Aggregates papers from arXiv and HuggingFace Daily Papers
- **Smart filtering**: Keyword-based filtering to reduce noise
- **LLM-powered ranking**: Uses AWS Bedrock (Claude) or Gemini to score papers based on your relevance specification
- **Automated summaries**: Generates concise summaries for top papers
- **Dual output formats**: JSON for automation, Markdown for human reading
- **Slack notifications**: Post highly relevant papers to Slack automatically
- **Caching**: Saves intermediate results for debugging and resume capability
- **Robust error handling**: Retry logic with exponential backoff
- **Multiple LLM providers**: Choose between AWS Bedrock or gemini-cli

## Architecture

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

## Setup

### 1. Install Dependencies

```bash
# Using uv
uv sync
```

### 2. Configure LLM Provider

The pipeline supports two LLM providers:

#### Option A: AWS Bedrock (Claude)

Configure your AWS credentials:

```bash
aws configure
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

**Note**: You need access to Claude models in AWS Bedrock. If you haven't submitted the use case form, set `mock_mode: true` in config.yaml for testing.

#### Option B: Gemini CLI

Install gemini-cli:

```bash
# Installation instructions for gemini-cli

# install Node.js

# Install gemini-cli
npm install -g @google/gemini-cli

# Run gemini to authenticate
gemini
```

In `config.yaml`, set:
```yaml
llm:
  provider: gemini
  gemini:
    model: gemini-2.5-flash-lite
```

### 3. Create Configuration

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to customize:
- **LLM provider**: Choose `bedrock` or `gemini`
- **ArXiv categories**: Which fields to monitor (cs.CV, cs.AI, etc.)
- **Keywords**: Include/exclude terms for filtering
- **LLM settings**: Provider-specific configuration (model ID, region, etc.)
- **Output settings**: Top N papers, score threshold
- **Slack notifications**: Enable and configure webhook (optional)

### 4. Customize Relevance Specification

Edit `prompts/spec.md` to define what papers are relevant to your research. The LLM uses this specification to score papers on a 1-5 scale.

### 5. (Optional) Configure Slack Notifications

To receive notifications for highly relevant papers:

1. **Create a Slack webhook**:
   - Go to https://api.slack.com/messaging/webhooks
   - Create a new webhook for your workspace
   - Copy the webhook URL

2. **Set the webhook URL** (recommended: use environment variable):
   ```bash
   export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```
   
   Or add it to `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and add your webhook URL
   ```

3. **Enable Slack in config.yaml**:
   ```yaml
   notifications:
     slack:
       enabled: true
       min_score: 4.5  # Only post papers scoring 4.5 or higher
       channel: "#research-papers"  # Optional
   ```

**Security Note**: Never commit webhook URLs to git. Use environment variables or add `.env` to `.gitignore`.

## Usage

### Run for Yesterday's Papers

```bash
uv run main.py
```

### Run for Specific Date

```bash
uv run main.py --date 2026-02-20
```

### Force Re-run (Ignore Cache)

```bash
uv run main.py --skip-cache
```

### Use Custom Config

```bash
uv run main.py --config my_config.yaml
```

## Pipeline Stages

### 1. Fetch Stage
- Fetches papers from arXiv (by category and date)
- Scrapes HuggingFace Daily Papers
- Deduplicates by arXiv ID (prefers arXiv version with abstract)

### 2. Filter Stage
- Applies keyword matching on title and abstract
- Excludes papers matching exclusion keywords
- Reduces candidate set for LLM ranking

### 3. Ranking Stage
- Batches papers (5-10 per batch)
- Sends to LLM provider with relevance specification
- Scores each paper on 1-5 scale
- Sorts by relevance score

### 4. Summary Stage
- Selects top papers using hybrid logic:
  - Top N papers by score, OR
  - All papers with score ≥ threshold
  - Whichever yields more papers
- Generates 2-3 sentence summaries via LLM

### 5. Report Stage
- Generates JSON report with all paper metadata
- Generates Markdown report grouped by score tier
- Saves to `reports/YYYY-MM-DD.{json,md}`

## Output

### JSON Report
```json
{
  "date": "2026-02-20",
  "paper_count": 5,
  "papers": [
    {
      "id": "2602.12345",
      "title": "Paper Title",
      "authors": ["Author 1", "Author 2"],
      "relevance_score": 5.0,
      "summary": "Brief summary...",
      ...
    }
  ]
}
```

### Markdown Report
```markdown
# Daily Paper Report - 2026-02-20

**Total Papers:** 5

## ⭐ Must-Read Papers (Score: 5)

### [Paper Title](https://arxiv.org/abs/2602.12345)

**Authors:** Author 1, Author 2

**Score:** 5.0 | **Source:** arxiv

**Summary:** Brief summary of the paper...

---
```

## Caching

Intermediate results are cached in `cache/` directory:
- `fetch_YYYY-MM-DD.json`: Raw papers from sources
- `filtered_YYYY-MM-DD.json`: After keyword filtering
- `ranked_YYYY-MM-DD.json`: After LLM scoring
- `summarized_YYYY-MM-DD.json`: After summary generation

Use `--skip-cache` to force re-run all stages.

## Logging

Logs are saved to `logs/pipeline_YYYY-MM-DD.log` with:
- Stage start/end times
- Paper counts at each stage
- API call successes/failures
- Error summaries

## Troubleshooting

### Bedrock Access Error
If you see "Model use case details have not been submitted":
1. Fill out the Anthropic use case form in AWS Console
2. Wait 15 minutes for approval
3. Or set `mock_mode: true` in config.yaml for testing

### Gemini CLI Not Found
If you see "gemini not found":
1. Install gemini: `npm install -g @google/gemini-cli`
2. Verify installation: `which gemini`
3. Or use `mock_mode: true` for testing

### Choosing Between Providers
**Use AWS Bedrock when:**
- You have AWS infrastructure already
- You need enterprise-grade SLAs
- You want Claude models specifically

**Use Gemini when:**
- You prefer Google's models
- You want simpler CLI-based integration
- You're already using Google Cloud services

### No Papers Found
- Check that the date has papers (arXiv updates daily)
- Verify arXiv categories in config.yaml
- Try a different date

### No Papers Pass Filter
- Review your include/exclude keywords
- Check that keywords match your research area
- Look at `cache/fetch_*.json` to see raw papers

### Slack Notifications Not Working
If papers aren't posting to Slack:
1. **Check webhook URL**: Verify it's correct and not expired
2. **Test webhook**: Use `curl` to test:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test message"}' \
     YOUR_WEBHOOK_URL
   ```
3. **Check min_score**: Papers must score >= `min_score` to be posted
4. **Check enabled flag**: Ensure `notifications.slack.enabled: true`
5. **Check logs**: Look in `logs/pipeline_*.log` for error messages
6. **Environment variable**: If using `SLACK_WEBHOOK_URL`, verify it's set:
   ```bash
   echo $SLACK_WEBHOOK_URL
   ```

### Slack Rate Limiting
If you see rate limit errors:
- The pipeline already includes 1-second delays between posts
- Reduce the number of papers by increasing `min_score`
- Slack webhooks allow ~1 message per second

## Customization

### Add New Paper Sources
1. Create a new tool in `tools/` (e.g., `semantic_scholar_tool.py`)
2. Update `pipeline/fetch_stage.py` to call your tool
3. Add configuration in `config.yaml`

### Change Scoring Logic
Edit `prompts/spec.md` to adjust:
- Core focus areas
- Priority topics
- Scoring rubric (1-5 scale definitions)

### Modify Report Format
Edit `pipeline/report_stage.py`:
- `generate_markdown_report()` for Markdown output
- `generate_json_report()` for JSON structure

## Spec Refinement Workflow

The relevance specification is the key to accurate paper scoring. Over time, you'll want to refine it based on misclassified papers. The refinement workflow helps you iteratively improve scoring accuracy.

### Setup

1. **Create a private spec directory** (outside the repo):
   ```bash
   mkdir -p ~/my-research-specs
   cp prompts/spec.example.md ~/my-research-specs/spec.md
   # Edit spec.md with your actual research focus
   ```

2. **Update config.yaml** to point to your spec:
   ```yaml
   spec:
     path: /home/user/my-research-specs/spec.md
     test_cases_path: /home/user/my-research-specs/test-cases.yaml
     backup_dir: /home/user/my-research-specs/backups
   ```

3. **Create test cases** from papers you've reviewed:
   ```yaml
   # ~/my-research-specs/test-cases.yaml
   version: 1.0
   test_cases:
     - id: "2401.12345"
       title: "Paper Title"
       abstract: "Paper abstract..."
       expected_score: 5
       notes: "Why this should score 5"
     
     - id: "2401.67890"
       title: "Another Paper"
       abstract: "Abstract..."
       expected_score: 2
       notes: "Not relevant because..."
   ```

### Refinement Cycle

1. **Run tests** to identify misclassifications:
   ```bash
   us run -m tools.test_scoring --test-file ~/my-research-specs/test-cases.yaml test
   ```
   
   This outputs:
   - Mean Absolute Error (MAE)
   - Root Mean Square Error (RMSE)
   - Accuracy (±0.5 points)
   - List of failed test cases (error > 1.0)

2. **Export failures** for refinement:
   ```bash
   uv run -m tools.test_scoring export-failures \
       --test-file ~/my-research-specs/test-cases.yaml \
       --export failures.json
   ```

3. **Refine the spec** using LLM analysis:
   ```bash
   uv run -m tools.refine_spec \
       --spec ~/my-research-specs/spec.md \
       --underscored underscored.json \
       --overscored overscored.json \
       --output ~/my-research-specs/spec-refined.md
   ```
   
   The LLM analyzes misclassifications and suggests:
   - Missing signals to add
   - Stronger exclusion criteria
   - Updated scoring rubric
   - Concrete, actionable changes

4. **Review and apply** the refined spec:
   ```bash
   # Review the changes
   diff ~/my-research-specs/spec.md ~/my-research-specs/spec-refined.md
   
   # Backup the old version
   cp ~/my-research-specs/spec.md ~/my-research-specs/backups/spec-$(date +%Y%m%d).md
   
   # Apply the refinement
   mv ~/my-research-specs/spec-refined.md ~/my-research-specs/spec.md
   ```

5. **Retest** to verify improvement:
   ```bash
   python -m tools.test_scoring test --test-file ~/my-research-specs/test-cases.yaml
   ```

### Building Test Cases

Good test cases come from real papers you've reviewed:

**From daily reports:**
```bash
# Extract papers from a specific date
python -m tools.spec_utils extract-papers \
    --date 2026-02-20 \
    --output candidates.json
```

**Add to test cases:**
- Papers that scored too low (should be higher)
- Papers that scored too high (should be lower)
- Edge cases that are hard to classify
- Representative examples of each score tier (1-5)

**Best practices:**
- Include at least 20-30 test cases for meaningful metrics
- Balance across score tiers (don't just test 5s and 1s)
- Add notes explaining why each paper should get its expected score
- Update test cases as your research focus evolves

### Metrics Guide

- **MAE < 0.5**: Excellent accuracy
- **MAE 0.5-1.0**: Good accuracy, minor refinement needed
- **MAE > 1.0**: Significant refinement needed
- **Accuracy > 80%**: Most papers within ±0.5 points
- **RMSE**: Penalizes large errors more than MAE

### Tips

- Start with a small test set (10-15 papers) and grow it over time
- Refine incrementally - don't try to fix everything at once
- Keep backups of your spec before each refinement
- Re-run the pipeline on past dates after refinement to validate
- Update test cases when your research focus shifts

## License

MIT License - see LICENSE file for details
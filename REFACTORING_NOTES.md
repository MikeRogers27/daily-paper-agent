# Refactoring Notes: test_scoring.py to use rank_papers()

**Date:** 2026-02-22  
**Status:** ✅ Complete

## Summary

Refactored `test_scoring.py` to eliminate duplicate scoring logic by using the production `rank_papers()` function from `ranking_stage.py`. This ensures consistency between test scoring and production scoring.

## Changes Made

### 1. Moved `parse_llm_response()` to Shared Location
- **From:** `pipeline/bedrock_client.py` (provider-specific module)
- **To:** `pipeline/llm_client.py` (shared LLM utilities)
- **Reason:** Function is used by multiple modules, not specific to Bedrock

**Updated imports in:**
- `pipeline/bedrock_client.py` - Now imports from `llm_client`
- `pipeline/ranking_stage.py` - Now imports from `llm_client`

### 2. Extended TestCase Dataclass
Added optional fields to support conversion to Paper objects:
- `authors: list[str] = field(default_factory=list)` - Paper authors
- `url: str = ""` - Paper URL

**Backward compatible:** Existing test case YAML files work without these fields.

### 3. Added Conversion Function
Created `test_case_to_paper(tc: TestCase) -> Paper` to convert test cases to Paper objects:
- Maps TestCase fields to Paper fields
- Uses sensible defaults: `source="test"`, `published_date=None`, `tags=[]`
- Generates arXiv URL if no URL provided

### 4. Refactored Scoring Logic
**Before:**
```python
def score_test_cases(test_cases, spec_path, llm_client):
    spec = load_relevance_spec(spec_path)
    for tc in test_cases:
        # Individual scoring with custom prompt
        response = llm_client.invoke(prompt, system_prompt=spec)
        result = parse_llm_response(response)
        actual_scores[tc.id] = float(result.get("score", 0))
```

**After:**
```python
def score_test_cases(test_cases, config, llm_client):
    papers = [test_case_to_paper(tc) for tc in test_cases]
    ranked_papers = rank_papers(papers, config, llm_client)
    actual_scores = {p.id: p.relevance_score or 0.0 for p in ranked_papers}
```

**Benefits:**
- Uses production scoring logic (batching, prompts, spec loading)
- Eliminates code duplication
- Ensures test scoring matches production behavior
- Easier to maintain (one place to update scoring logic)

### 5. Updated CLI Interface
**Removed:** `--spec-path` argument (spec now loaded via config, matching production)  
**Preserved:** All other CLI functionality (test, export-failures, --test-file, --export)

### 6. Updated Test Case Example
Added documentation for optional fields in `tests/test-cases.example.yaml`:
```yaml
test_cases:
  - id: "2401.12345"
    title: "Your Paper Title"
    abstract: "Paper abstract..."
    expected_score: 5
    notes: "Why this should score 5"
    # Optional fields:
    # authors: ["Author One", "Author Two"]
    # url: "https://arxiv.org/abs/2401.12345"
```

## Files Modified

1. **pipeline/llm_client.py** - Added `parse_llm_response()` function
2. **pipeline/bedrock_client.py** - Removed `parse_llm_response()`, updated import
3. **pipeline/ranking_stage.py** - Updated import to use `llm_client`
4. **tools/test_scoring.py** - Major refactoring (see above)
5. **tests/test-cases.example.yaml** - Added optional fields documentation

## Testing

All integration tests pass:
- ✅ Imports work correctly
- ✅ `parse_llm_response()` accessible from all modules
- ✅ TestCase with optional fields works
- ✅ Conversion from TestCase to Paper works
- ✅ Test cases load correctly
- ✅ Config loading works

## Usage

### Before (still works, but --spec-path removed):
```bash
uv run -m tools.test_scoring test --test-file test-cases.yaml --spec-path prompts/spec.md
```

### After:
```bash
# Spec path now comes from config.yaml
uv run -m tools.test_scoring test --test-file test-cases.yaml
```

### With optional fields in test cases:
```yaml
test_cases:
  - id: "2401.12345"
    title: "Paper Title"
    abstract: "Abstract..."
    expected_score: 5
    authors: ["Author One", "Author Two"]  # Optional
    url: "https://arxiv.org/abs/2401.12345"  # Optional
```

## Benefits

1. **Single Source of Truth:** All scoring uses `rank_papers()` function
2. **Consistency:** Test scoring matches production scoring exactly
3. **Maintainability:** Changes to scoring logic only need to happen once
4. **Code Quality:** Reduced duplication, cleaner architecture
5. **Batching:** Test scoring now uses same efficient batching as production
6. **Shared Utilities:** `parse_llm_response()` in appropriate shared location

## Backward Compatibility

✅ **Preserved:**
- CLI commands (test, export-failures)
- Test report format (MAE, RMSE, accuracy)
- Metrics calculation
- Existing test case YAML files (new fields optional)

❌ **Removed:**
- `--spec-path` CLI argument (use config.yaml instead)

## Migration Guide

If you have existing test case files, no changes needed. To use new features:

1. **Add authors** (optional):
   ```yaml
   authors: ["Author One", "Author Two"]
   ```

2. **Add custom URL** (optional):
   ```yaml
   url: "https://example.com/paper"
   ```

3. **Remove --spec-path** from scripts:
   ```bash
   # Old
   uv run -m tools.test_scoring test --test-file cases.yaml --spec-path spec.md
   
   # New
   uv run -m tools.test_scoring test --test-file cases.yaml
   ```

## Future Enhancements

Potential improvements enabled by this refactoring:
- Test scoring can now use all `rank_papers()` features (batching, retries, etc.)
- Easy to add more Paper fields to TestCase if needed
- Can test different configs without changing test case files
- Easier to add new LLM providers (automatically work with test scoring)

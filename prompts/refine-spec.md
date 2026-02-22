# Relevance Specification Refinement

You are refining an academic paper relevance specification based on feedback from misclassified papers.

## Current Specification

{current_spec}

## Feedback: Papers That Scored Too LOW

These papers should have scored HIGHER but received low scores:

{underscored_papers}

## Feedback: Papers That Scored Too HIGH

These papers should have scored LOWER but received high scores:

{overscored_papers}

## Task

Analyze the misclassifications and produce a refined specification that:

1. **Identifies missing signals**: What patterns in the underscored papers should trigger higher scores?
2. **Strengthens exclusions**: What patterns in the overscored papers should trigger lower scores?
3. **Updates scoring rubric**: Adjust the 1-5 scale definitions for better accuracy
4. **Preserves core focus**: Don't drift from the original research area

## Output Format

Return the complete refined specification in the same markdown format as the input, with all sections preserved:
- Core Focus
- Priority Topics (High/Medium)
- Exclusions
- Modalities of Interest
- Methods of Interest
- Must-Have Signals
- Likely Irrelevant Signals
- Relevance Scoring Rubric

Focus on concrete, actionable changes that will improve scoring accuracy.

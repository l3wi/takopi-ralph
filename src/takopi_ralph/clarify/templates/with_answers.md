## Follow-up: Generate Stories

The user has answered your questions.

**User Answers:**
{{answers}}

**Current PRD:**
```json
{{prd_json}}
```

## Instructions

Based on the user's answers, generate appropriate user stories.

- NO more questions needed
- Generate stories that reflect the user's choices
- Ensure stories have specific acceptance criteria
- Prioritize logically (setup first, then features)

Respond with JSON containing only `analysis` and `suggested_stories` (empty questions array).

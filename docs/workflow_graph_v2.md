# PR Review Workflow Graph v2

## Overview

File-by-file processing with immediate GitHub publishing and LLM-driven search.

## Mermaid Diagram

```mermaid
flowchart TD
    START((Start)) --> extract_diff

    subgraph Init["Initialization"]
        extract_diff[/"📥 extract_diff<br/>Fetch PR files from GitHub"/]
        clone_repo[/"📂 clone_repo<br/>Shallow clone repo locally"/]
    end

    extract_diff -->|has files| clone_repo
    extract_diff -->|no code files| cleanup

    clone_repo --> get_next_file

    subgraph FileLoop["File Processing Loop"]
        get_next_file{{"📄 get_next_file<br/>Pop next file"}}
        analyze_file[/"🔍 analyze_file<br/>LLM detects breaking changes"/]
    end

    get_next_file -->|has file| analyze_file
    get_next_file -->|no more files| publish_summary

    analyze_file -->|no changes| get_next_file
    analyze_file -->|has changes| plan_search

    subgraph SearchLoop["Search Agent Loop"]
        plan_search[/"🧠 plan_search<br/>LLM plans search queries"/]
        execute_search[/"🔎 execute_search<br/>Ripgrep search"/]
        verify_impact[/"✅ verify_impact<br/>LLM verifies callers"/]
        next_change{{"➡️ next_change<br/>Next entity"}}
    end

    plan_search --> execute_search
    execute_search --> verify_impact

    verify_impact -->|need more search| plan_search
    verify_impact -->|more changes| next_change
    verify_impact -->|done| generate_review

    next_change --> plan_search

    subgraph Publish["Publishing"]
        generate_review[/"📝 generate_review<br/>LLM formats comments"/]
        publish_github[/"🐙 publish_github<br/>Post to PR immediately"/]
    end

    generate_review --> publish_github
    publish_github --> get_next_file

    subgraph Final["Finalization"]
        publish_summary[/"📢 publish_summary<br/>Slack notification"/]
        cleanup[/"🧹 cleanup<br/>Remove cloned repo"/]
    end

    publish_summary --> cleanup
    cleanup --> END((End))

    style Init fill:#e1f5fe
    style FileLoop fill:#fff3e0
    style SearchLoop fill:#f3e5f5
    style Publish fill:#e8f5e9
    style Final fill:#fce4ec
```

## Node Descriptions

| Node | Type | Description |
|------|------|-------------|
| `extract_diff` | GitHub API | Fetches all changed files in PR with content |
| `clone_repo` | Git | Shallow clone with `--depth 1 --filter=blob:limit=1m` |
| `get_next_file` | Control | Pops next file from queue, resets per-file state |
| `analyze_file` | LLM | Detects breaking changes (functions, constants, etc.) |
| `plan_search` | LLM | Decides search queries based on language/entity |
| `execute_search` | Ripgrep | Fast local search, no rate limits |
| `verify_impact` | LLM | Confirms which callers will actually break |
| `next_change` | Control | Moves to next entity in current file |
| `generate_review` | LLM | Formats review comments with context |
| `publish_github` | GitHub API | Posts comments immediately to PR |
| `publish_summary` | Slack | Sends final summary notification |
| `cleanup` | Filesystem | Removes cloned repo |

## State Flow

```
PRContext → file_diffs → pending_files → current_file
                                              ↓
                                        file_changes → current_change
                                              ↓
                                        search_plan → search_results
                                              ↓
                                        verified_callers → file_breaking_changes
                                              ↓
                                        file_comments → published_comments
                                              ↓
                                        all_breaking_changes → all_comments
```

## Key Features

1. **File-by-file processing**: Each file is fully processed before moving to next
2. **Immediate publishing**: Comments posted to GitHub as soon as ready
3. **LLM-driven search**: AI decides what to search based on language/context
4. **Search refinement loop**: Can request additional searches if needed
5. **Automatic cleanup**: Cloned repo removed on completion or error

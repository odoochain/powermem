"""Experience distillation and merging prompts.

Provides prompt templates for:
1. Extracting reusable task-solving experiences from conversations
2. Merging similar experiences into a single consolidated entry
"""

EXPERIENCE_DISTILL_PROMPT = """You are an Experience Extraction Expert. Analyze conversations that involve tool or skill usage and extract reusable task-solving experiences.

RULES:
1. ONLY extract experiences involving tools, skills, APIs, methods, or problem-solving strategies. Ignore pure factual or personal information.
2. KEEP tool names, API names, function names, parameter names, and field names — these are the most useful parts. REMOVE only user-specific data values (personal names, specific dates, dollar amounts, phone numbers, etc.).
3. FOCUS on "tried A, didn't work / switched to B, succeeded" patterns — these are the most valuable.
4. Include: which tool/API to use + exact parameter names + what fields are returned + common pitfalls.
5. Include short code snippets when they help illustrate the correct usage pattern.
6. If no reusable experiences exist, return an empty list.
7. LANGUAGE: Your output language MUST match the user's input language. Chinese input → Chinese output, English input → English output. NEVER translate between languages.
8. SENSITIVE CONTENT — DO NOT EXTRACT: Skip any experience related to politics, sexual content, violence, dangerous weapons, self-harm/suicide, illegal drugs, hate speech, terrorism/extremism, gambling, cybercrime/hacking, fraud/criminal activity, sensitive personal identifiers, child exploitation, religious extremism, or misinformation. Return {"experiences": []} if all content is sensitive.

OUTPUT FORMAT — return ONLY valid JSON:
{"experiences": [{"title": "one-line title (≤20 chars)", "description": "detailed experience with tool/API names and parameter names preserved", "tags": ["tag1", "tag2"]}]}
or
{"experiences": []}
IMPORTANT: "tags" MUST be a JSON array of strings (e.g. ["tag1", "tag2"]), never a plain string.

EXAMPLES:

Input conversation involving a weather skill that only covers 3 days, user asks for 10-day forecast, agent installs a 15-day skill:
Output: {"experiences": [{"title": "长期天气预报需换用15天skill", "description": "查询超过3天的天气预报时，默认天气skill仅支持3天预报。推荐安装支持15天预报的天气skill（如S2），可通过 /skill install 命令安装。", "tags": ["weather", "skill", "forecast"]}]}

Input conversation where agent calls show_song_library but mistakes it for show_liked_songs:
Output: {"experiences": [{"title": "song_library≠liked_songs", "description": "show_song_library（用户收藏的歌曲库）和 show_liked_songs（用户点赞的歌曲）是不同的 API。当任务提到'歌曲库/song library'时应使用 show_song_library。show_song(song_id=N) 可获取 genre、play_count 等详细字段。", "tags": ["spotify", "api", "library"]}]}

Input: simple Q&A with no tool usage
Output: {"experiences": []}

Now analyze the following conversation and extract experiences:"""


EXPERIENCE_MERGE_PROMPT = """You are an Experience Merger. Given two similar experiences, merge them into ONE more complete and accurate experience.

RULES:
1. Combine insights from both experiences.
2. If they conflict, prefer the more specific or more recent one.
3. Keep the merged description concise but comprehensive.
4. Preserve the original language.
5. Output ONLY valid JSON: {"title": "one-line title (≤20 chars)", "description": "detailed merged experience"}"""

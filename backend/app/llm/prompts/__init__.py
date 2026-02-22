from app.llm.prompts.table_interpretation import build_table_prompt
from app.llm.prompts.figure_interpretation import build_figure_prompt
from app.llm.prompts.general_summary import build_general_summary_prompt
from app.llm.prompts.discussion import build_discussion_prompt
from app.llm.prompts.conclusions import build_conclusions_prompt


__all__ = [
    "build_table_prompt",
    "build_figure_prompt",
    "build_general_summary_prompt",
    "build_discussion_prompt",
    "build_conclusions_prompt",
]

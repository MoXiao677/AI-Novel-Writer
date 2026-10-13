"""文风与写作规则管理。"""

from novel_writer.application.fields import check_fields, text

MODULE = {"id": "writing_rules", "name": "文风与写作规则管理", "status": "ready", "description": "保存叙事视角、节奏、禁用表达和作者偏好。"}


def save(state, values):
    check_fields(values, {"content"})
    state["writing_rules"] = text(values.get("content"), "写作规则")

"""世界观与设定管理，当前以可自由编辑的资料文本保存。"""

from novel_writer.application.fields import check_fields, text

MODULE = {"id": "worldbuilding", "name": "世界观与设定管理", "status": "ready", "description": "手动维护地点、组织、力量体系与背景资料。"}


def save(state, values):
    check_fields(values, {"content"})
    state["worldbuilding"] = text(values.get("content"), "世界观设定")

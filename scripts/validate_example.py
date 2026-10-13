"""只读校验虚构示例；从任何工作目录运行均不会修改小说文件。"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from novel_writer.domain.models import DataValidationError
from novel_writer.storage.json_codec import document_from_json, document_to_json, read_document


def main() -> int:
    try:
        document = read_document(PROJECT_ROOT / "examples" / "sample-novel" / "novel.json")
        restored = document_from_json(document_to_json(document))
        if restored != document:
            raise DataValidationError("JSON 转换前后的数据不一致")
    except (DataValidationError, OSError, UnicodeError) as error:
        print(f"示例校验失败：{error}", file=sys.stderr)
        return 1
    print(f"示例校验通过：《{document.project.title}》")
    print(f"人物：{len(document.characters)}；章节：{len(document.chapters)}；历史版本：{len(document.versions)}")
    print("数据类型、编号关联、版本链及 JSON 往返转换均通过检查。")
    print("本命令只读取示例，不调用 AI，也不保存或覆盖文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

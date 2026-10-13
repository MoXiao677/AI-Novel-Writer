"""仅绑定本机的标准库 HTTP 界面，所有写操作经过会话令牌和业务层。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlsplit

from novel_writer.application.service import NovelService
from novel_writer.application.skill_import import MODULE as SKILLS_MODULE, SkillLibrary
from novel_writer.storage.sqlite_repository import ConflictError, SQLiteRepository

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 12 * 1024 * 1024


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, database_path, port):
        self.database_path = Path(database_path).resolve()
        self.service = NovelService(SQLiteRepository(self.database_path))
        self.skills = SkillLibrary(self.database_path)
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 正文、编号与错误内容不输出到终端日志。
        pass

    def send_body(self, status, body: bytes, content_type: str, *, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value, *, filename=None):
        self.send_body(status, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"),
                       "application/json; charset=utf-8", filename=filename)

    def allowed_request(self, *, write=False):
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        if host not in hosts:
            self.send_json(403, {"error": "只允许从本机地址访问"})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{item}" for item in hosts}:
            self.send_json(403, {"error": "拒绝其他网站的请求"})
            return False
        if write and not secrets.compare_digest(self.headers.get("X-Novel-Token", ""), self.server.token):
            self.send_json(403, {"error": "页面会话已失效，请保留输入后重新打开页面"})
            return False
        return True

    def do_GET(self):
        if not self.allowed_request():
            return
        path = urlsplit(self.path).path
        service = self.server.service
        try:
            if path == "/api/session":
                self.send_json(200, {"token": self.server.token})
            elif path == "/api/projects":
                self.send_json(200, service.list_projects())
            elif path == "/api/modules":
                self.send_json(200, [*service.modules(), SKILLS_MODULE])
            elif path == "/api/settings":
                self.send_json(200, {**service.settings(), "database_path": str(self.server.database_path)})
            elif path == "/api/skills":
                self.send_json(200, self.server.skills.list_skills())
            elif path.startswith("/api/skills/") and len(path.strip("/").split("/")) == 3:
                self.send_json(200, self.server.skills.get(path.split("/")[-1]))
            elif path.startswith("/api/projects/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    self.send_json(200, service.get(parts[2]))
                elif len(parts) == 4 and parts[3] == "export":
                    self.send_json(200, service.get(parts[2]), filename="novel-workspace.json")
                else:
                    self.send_json(404, {"error": "找不到这个入口"})
            else:
                assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                          "/style.css": ("style.css", "text/css"), "/favicon.svg": ("favicon.svg", "image/svg+xml"),
                          "/guide.html": ("guide.html", "text/html")}
                if path not in assets:
                    self.send_json(404, {"error": "找不到这个入口"})
                else:
                    name, mime = assets[path]
                    self.send_body(200, (STATIC / name).read_bytes(), mime + "; charset=utf-8")
        except KeyError:
            self.send_json(404, {"error": "找不到这份资料"})
        except (ValueError, OSError, sqlite3.Error):
            self.send_json(500, {"error": "读取失败，请检查数据文件；现有数据没有被修改"})

    def do_POST(self):
        if not self.allowed_request(write=True):
            return
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("写操作必须提交 JSON")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.send_json(413, {"error": "请求为空或超过 12 MiB 限制，请拆分章节"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if type(payload) is not dict:
                raise ValueError("提交内容必须是对象")
            path = urlsplit(self.path).path
            if path == "/api/projects":
                self.send_json(201, self.server.service.create(**payload))
                return
            if path == "/api/skills/import":
                if set(payload) != {"files"}:
                    raise ValueError("导入参数必须只包含 files")
                self.send_json(201, self.server.skills.import_files(payload["files"]))
                return
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "projects"] or parts[3] != "actions":
                self.send_json(404, {"error": "找不到这个入口"})
                return
            if set(payload) != {"action", "fields", "expected_revision"}:
                raise ValueError("操作参数不完整或含未知字段")
            state = self.server.service.execute(parts[2], payload["action"], payload["fields"], expected_revision=payload["expected_revision"])
            self.send_json(200, state)
        except ConflictError as error:
            self.send_json(409, {"error": str(error)})
        except KeyError:
            self.send_json(404, {"error": "找不到这本小说"})
        except (ValueError, TypeError, UnicodeError) as error:
            self.send_json(422, {"error": str(error)})
        except (sqlite3.Error, OSError):
            self.send_json(500, {"error": "保存失败，事务已回滚。请保留页面输入并检查磁盘空间和数据库文件"})


def create_server(database_path: str | Path, *, port=8765) -> LocalServer:
    return LocalServer(database_path, port)

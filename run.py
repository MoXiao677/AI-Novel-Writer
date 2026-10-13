"""无需安装依赖即可从源码启动本地写作工作台。"""

import argparse
from pathlib import Path
import sqlite3
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))


def port_number(value):
    port = int(value)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError('端口必须在 0 至 65535 之间')
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(description='启动 AI-Novel-Writer 离线写作工作台')
    parser.add_argument('--port', type=port_number, default=8765, help='本机端口，默认 8765；0 表示自动选择')
    parser.add_argument('--database', type=Path, default=ROOT / 'data' / 'novels.sqlite3', help='数据库文件路径')
    parser.add_argument('--no-browser', action='store_true', help='只启动服务，不自动打开浏览器')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        print('请使用 Python 3.11 或更高版本启动。', file=sys.stderr)
        return 1
    from novel_writer.ui.server import create_server
    try:
        server = create_server(args.database, port=args.port)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f'启动失败：{error}。请检查数据库位置、磁盘空间和端口；端口被占用时可加 --port 8766。', file=sys.stderr)
        return 1
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print('AI-Novel-Writer · 离线写作工作台', flush=True)
    print(url, flush=True)
    print(f'数据保存在：{server.database_path}', flush=True)
    print('请保留这个窗口。完成写作后先点击页面保存，再按 Ctrl+C 停止软件。', flush=True)
    opener = None
    if not args.no_browser:
        opener = threading.Timer(0.4, lambda: webbrowser.open(url))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print('\n软件已停止。已经保存的内容保留在数据库中。', flush=True)
    finally:
        if opener:
            opener.cancel()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

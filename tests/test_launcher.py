"""从仓库外启动软件，验证公共入口与保存位置。"""

import http.client
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_help_does_not_start_service_or_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'run.py'), '--help'],
                                    cwd=directory, capture_output=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--no-browser', result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_launcher_runs_from_other_directory_and_uses_requested_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'saved' / 'novels.sqlite3'
            process = subprocess.Popen([sys.executable, '-X', 'utf8', '-u', str(ROOT / 'run.py'),
                                        '--no-browser', '--port', '0', '--database', str(database)],
                                       cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            try:
                lines = queue.Queue()
                def collect():
                    for line in process.stdout:
                        if line.startswith('http://127.0.0.1:'):
                            lines.put(line.strip())
                            return
                    lines.put(None)
                reader = threading.Thread(target=collect, daemon=True)
                reader.start()
                url = lines.get(timeout=10)
                self.assertIsNotNone(url, '启动入口没有提供本机地址')
                connection = http.client.HTTPConnection('127.0.0.1', urlsplit(url).port, timeout=5)
                try:
                    connection.request('GET', '/api/settings')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    settings = json.loads(response.read())
                    self.assertEqual(Path(settings['database_path']), database)
                    self.assertFalse(settings['model_calls_enabled'])
                    self.assertTrue(database.is_file())
                finally:
                    connection.close()
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=10)
                reader.join(timeout=2)


if __name__ == '__main__':
    unittest.main()

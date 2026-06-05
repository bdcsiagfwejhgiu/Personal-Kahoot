import os
import subprocess
import json
import ssl
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class KahootConnector:
    CHALLENGE_API_URL = "https://kahoot.it/rest/challenges/pin/"

    def __init__(self):
        # no heavy imports here to keep the module lightweight
        pass

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9'
        }

    def resolve_pin(self, pin: str):
        if not pin.isdigit():
            return {'error': 'PIN must contain only digits'}

        url = f"{self.CHALLENGE_API_URL}{pin}"
        req = Request(url, headers=self._get_headers())
        try:
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if 'id' in data:
                    return {'quiz_id': data['id']}
                return {'error': 'No quiz ID found in response'}
        except HTTPError as e:
            body = None
            try:
                body = e.read().decode('utf-8', errors='ignore')
                body_json = json.loads(body)
                if isinstance(body_json, dict) and 'error' in body_json:
                    return {'error': f'HTTP Error: {e.code} - {body_json["error"]}'}
            except Exception:
                pass
            if e.code == 404:
                return {'error': 'Quiz not found. The PIN may be incorrect or the game inactive.'}
            return {'error': f'HTTP Error: {e.code}'}
        except URLError as e:
            return {'error': f'Connection error: {e.reason}'}
        except Exception as e:
            return {'error': str(e)}

    def _project_root(self):
        return os.path.dirname(os.path.abspath(__file__))

    def _node_module_exists(self, module_name: str) -> bool:
        module_path = os.path.join(self._project_root(), 'node_modules', module_name)
        if not os.path.isdir(module_path):
            return False
        entries = os.listdir(module_path)
        return any(entry.endswith('.js') for entry in entries)

    def _ensure_node_modules(self):
        if self._node_module_exists('kahoot.js-latest'):
            return True, None
        if self._node_module_exists('kahoot.js-updated'):
            return True, None
        if self._node_module_exists('kahoot.js'):
            return True, None

        project_root = self._project_root()
        install_cmd = ['npm', 'install', 'kahoot.js-latest', '--no-save', '--no-fund', '--no-audit']

        try:
            proc = subprocess.run(
                install_cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
        except FileNotFoundError:
            return False, 'npm not found. Install Node.js and npm.'
        except Exception as e:
            return False, str(e)

        if proc.returncode != 0:
            return False, proc.stderr.strip() or proc.stdout.strip() or 'npm install failed'

        if self._node_module_exists('kahoot.js-updated') or self._node_module_exists('kahoot.js'):
            return True, None

        return False, 'Node modules were installed but kahoot.js-updated or kahoot.js still cannot be found.'

    def join(self, pin: str, nickname: str = None):
        """Spawn the Node joiner. Returns (process, message).
        Ensure Node and kahoot.js-updated are installed for this to work.
        """
        node_script = os.path.join(os.path.dirname(__file__), 'join_kahoot.js')
        if not os.path.exists(node_script):
            return None, f"join script not found: {node_script}"

        ok, error = self._ensure_node_modules()
        if not ok:
            return None, f"Missing Node dependencies: {error}"

        cmd = ['node', node_script, pin]
        if nickname:
            cmd.append(nickname)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(node_script),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            return proc, 'started'
        except FileNotFoundError:
            return None, 'Node.js not found. Install Node to join.'
        except Exception as e:
            return None, str(e)


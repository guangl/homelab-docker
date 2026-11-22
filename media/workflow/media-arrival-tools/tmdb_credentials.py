from getpass import getpass
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SECRET_FILE = Path(__file__).resolve().parents[3] / 'secrets' / 'media-arrival-tmdb'
RETIRED_FINGERPRINT = SECRET_FILE.with_suffix('.retired')
TMDB = 'https://api.themoviedb.org/3'


def request_parts(route, language, credential):
    params = {'language': language}
    headers = {'User-Agent': 'homelab-media-monitor'}
    if re.fullmatch(r'[0-9a-fA-F]{32}', credential):
        params['api_key'] = credential
    elif re.fullmatch(r'[\w-]+\.[\w-]+\.[\w-]+', credential, flags=re.ASCII):
        headers['Authorization'] = 'Bearer ' + credential
    else:
        raise ValueError('TMDB_PRIVATE_CREDENTIAL_INVALID')
    return f'{TMDB}/{route}?{urlencode(params)}', headers


def tmdb_request(route, language, requester):
    try:
        credential = SECRET_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        raise ValueError('TMDB_PRIVATE_CREDENTIAL_MISSING') from None
    url, headers = request_parts(route, language, credential)
    return requester(url, headers=headers)


def install(credential):
    url, headers = request_parts('tv/1399', 'zh-CN', credential)
    if RETIRED_FINGERPRINT.is_file() and hashlib.sha256(credential.lower().encode()).hexdigest() == RETIRED_FINGERPRINT.read_text().strip():
        raise ValueError('这把密钥已从番剧任务退役，请输入另一把密钥。')
    if SECRET_FILE.exists() and SECRET_FILE.read_text(encoding='utf-8').strip() == credential:
        raise ValueError('该密钥已在使用中。')
    try:
        with urlopen(Request(url, headers=headers), timeout=10) as response:
            if response.status != 200:
                raise ValueError(f'TMDB 验证失败（HTTP {response.status}）。')
    except HTTPError as error:
        raise ValueError(f'TMDB 验证失败（HTTP {error.code}）。') from None
    except OSError:
        raise ValueError('无法连接 TMDB 验证密钥。') from None

    SECRET_FILE.parent.mkdir(mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=SECRET_FILE.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(credential + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, SECRET_FILE)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise SystemExit('请在终端中使用交互式无回显输入。')
    try:
        install(getpass('TMDB 新 API Key 或 Read Access Token（输入不回显）: ').strip())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except (EOFError, KeyboardInterrupt):
        raise SystemExit('已取消。') from None
    print('TMDB 验证成功，密钥已写入 NAS 私有配置。')

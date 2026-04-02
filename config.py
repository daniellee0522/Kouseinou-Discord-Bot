import json
from pathlib import Path

_base = Path(__file__).parent
DATA_DIR = _base / 'data'

try:
    with open(DATA_DIR / 'token.json', 'r', encoding='utf8') as _f:
        _cfg = json.load(_f)
except FileNotFoundError:
    raise SystemExit("找不到 data/token.json，請複製 token.json.example 並填入設定值")

TOKEN                   = _cfg['token']
OPENAI_API_KEY          = _cfg.get('openai_api_key', '')
CWA_API_TOKEN           = _cfg.get('cwa_api_token', '')
BAHA_USERNAME           = _cfg.get('baha_username', '')
BAHA_PASSWORD           = _cfg.get('baha_password', '')
OWNER_ID                = int(_cfg.get('owner_id', 0))
GUILD_IDS               = _cfg.get('guild_ids', [])
JM_LOG_CHANNEL_ID       = int(_cfg.get('jm_log_channel_id', 0))
NH_PROXY_URL            = _cfg.get('nh_proxy_url', '')
PIC_PROXY_URL           = _cfg.get('pic_proxy_url', '')
MEDIA_BASE_URL          = _cfg.get('media_base_url', '')
VIDEO_PATH              = _cfg.get('video_path', str(_base / 'videos'))
MD5_JSON_PATH           = _cfg.get('md5_json_path', str(DATA_DIR / 'md5.json'))
SHEET_USER_COLUMNS_CHECK = {int(k): v for k, v in _cfg.get('sheet_user_columns_check', {}).items()}
SHEET_USER_COLUMNS_PAY  = {int(k): v for k, v in _cfg.get('sheet_user_columns_pay', {}).items()}

import json
from pathlib import Path
from bilibili_api import Credential, login_v2
from config import CREDENTIAL_FILE

try:
    from bilibili_api import select_client
    select_client("httpx")
except Exception:
    pass


def load_credential() -> Credential | None:
    if not CREDENTIAL_FILE.exists():
        return None
    data = json.loads(CREDENTIAL_FILE.read_text(encoding="utf-8"))
    sessdata = (data.get("sessdata") or "").strip()
    bili_jct = (data.get("bili_jct") or "").strip()
    buvid3 = (data.get("buvid3") or "").strip()
    if not sessdata:
        return None
    return Credential(sessdata=sessdata, bili_jct=bili_jct, buvid3=buvid3)


def save_credential(credential: Credential):
    data = {
        "sessdata": credential.sessdata or "",
        "bili_jct": credential.bili_jct or "",
        "buvid3": credential.buvid3 or "",
    }
    CREDENTIAL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_credential():
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()


async def login_qrcode() -> dict:
    login = login_v2.QrCodeLogin()
    await login.fetch_qrcode()
    qr_url = login.get_qrcode_url()
    return {
        "qrcode_url": qr_url,
        "login_obj": login,
    }


async def poll_qrcode(login_obj) -> Credential | None:
    try:
        await login_obj.check_login()
        if login_obj.get_credential():
            cred = login_obj.get_credential()
            save_credential(cred)
            return cred
    except Exception:
        pass
    return None


def create_credential_from_manual(sessdata: str, bili_jct: str = "", buvid3: str = "") -> Credential:
    cred = Credential(sessdata=sessdata.strip(), bili_jct=bili_jct.strip(), buvid3=buvid3.strip())
    save_credential(cred)
    return cred

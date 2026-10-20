import asyncio
import sqlite3
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, CopyTextButton, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
import re
import json
import time
import logging
from collections import deque
import os
from io import StringIO
import csv
import pyotp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════
#                    CONFIG
# ════════════════════════════════════════════════════
TOKEN = "8835032643:AAE4AEZUMGsOC-Rr_ICYMSAUIeO-F6yD0UI"

# ─── Lamix SMS Panel API ───
LAMIX_BASE_URL = "https://panel.lamix.org"
LAMIX_API_TOKEN = "PDRCif2kg-Bdrlo1rWVouEeiEliVVb2HP_SBfOnHX10"   # ← এখানে আপনার Lamix API টোকেন বসান

OTP_GROUP_LINK = "https://t.me/SKYOTP_SKY"
DB_PATH = "otp_pro_panel.db"
BACKUP_DIR = "db_backups"

os.makedirs(BACKUP_DIR, exist_ok=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ════════════════════════════════════════════════════
#                  DATABASE SETUP
# ════════════════════════════════════════════════════
db = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = db.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=NORMAL;")
cursor.execute("PRAGMA temp_store=MEMORY;")
db.commit()

_TABLES = [
    "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)",
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, username TEXT, fullname TEXT)",
    "CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)",
    "CREATE TABLE IF NOT EXISTS otp_success_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, phone_number TEXT, otp_code TEXT, timestamp TEXT)",
    "CREATE TABLE IF NOT EXISTS manual_services (id INTEGER PRIMARY KEY AUTOINCREMENT, service_name TEXT, country_name TEXT, flag TEXT, give_amount INTEGER DEFAULT 1, price REAL DEFAULT 0.0, stock INTEGER DEFAULT 0, cooldown INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS manual_numbers (id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER, number TEXT, FOREIGN KEY(service_id) REFERENCES manual_services(id))",
]
for _sql in _TABLES:
    cursor.execute(_sql)

cursor.execute("INSERT OR IGNORE INTO config VALUES ('maintenance_mode', 'off')")
cursor.execute("INSERT OR IGNORE INTO admins VALUES ('6820798198')")
cursor.execute("INSERT OR IGNORE INTO admins VALUES ('7689218221')")

_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN active_manual TEXT",
    "ALTER TABLE users ADD COLUMN manual_cooldowns TEXT",
    "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN join_date TEXT",
    "ALTER TABLE manual_services ADD COLUMN cooldown INTEGER DEFAULT 0",
    "ALTER TABLE manual_services ADD COLUMN price REAL DEFAULT 0.0",
    "ALTER TABLE otp_success_logs ADD COLUMN service_name TEXT",
]
for _m in _MIGRATIONS:
    try:
        cursor.execute(_m)
    except Exception:
        pass

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_manual_svc_name ON manual_services(service_name)",
    "CREATE INDEX IF NOT EXISTS idx_otp_logs_user ON otp_success_logs(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_otp_logs_time ON otp_success_logs(timestamp)",
]
for _idx in _INDEXES:
    cursor.execute(_idx)

db.commit()

# ════════════════════════════════════════════════════
#               CUSTOM EMOJI IDs
# ════════════════════════════════════════════════════
E = {
    "phone": "6204108584381322968", "lock": "5251203410396458957",
    "folder": "5282843764451195532", "chart": "5231200819986047254",
    "gear": "6267097569722111582", "planet": "6285048454255220485",
    "globe": "5447410659077661506", "channel": "5458603043203327669",
    "chat": "5443038326535759644", "shopping": "5229064374403998351",
    "facebook": "5389064576333527180", "whatsapp": "5233354831984353090",
    "instagram": "5364310996179503764", "telegram": "5424818078833715060",
    "fire": "5424972470023104089", "success": "5273806972871787310",
    "error": "5271934564699226262", "trophy": "5440539497383087970",
    "users": "6307777408300753473", "search": "5231012545799666522",
    "broadcast": "5424818078833715060", "add": "5397916757333654639",
    "delete": "5445267414562389170", "back": "5332348837405145999",
    "ban": "5240241223632954241", "maintenance": "5366231924597604153",
    "signal": "5424818078833715060", "store": "5416041192905265756",
    "next": "5416117059207572332", "waiting": "5386367538735104399",
    "cat": "5285288477015949061", "star": "5438496463044752972",
    "diamond": "5427168083074628963", "gift": "5309849913218071967",
    "package": "5348149223223211884", "money": "5388622778817589921",
    "bank": "6258153613860805124", "card": "5389078268689265131",
    "red_circle": "5411225014148014586", "green_circle": "5416081784641168838",
    "warning": "5447644880824181073", "info": "5334544901428229844",
    "refresh": "5375338737028841420", "database": "5282843764451195532",
    "backup": "5348149223223211884", "restore": "5375338737028841420",
    # Country flags
    "flag_af": "5291937511591925566", "flag_al": "5294202819077756005",
    "flag_dz": "5294048127240655242", "flag_ar": "5292208210495689627",
    "flag_am": "5291978717508164018", "flag_au": "5294444247779399477",
    "flag_at": "5291975174160145850", "flag_az": "5294323533428579078",
    "flag_bh": "5294108398516720753", "flag_bd": "5291824686097827834",
    "flag_be": "5291774466043435275", "flag_br": "5291892229751723900",
    "flag_bn": "5292098293692650297", "flag_bg": "5294308947719640437",
    "flag_ca": "5292290347450259214", "flag_cl": "5294231037012888049",
    "flag_cn": "5294068833277990704", "flag_co": "5294010206974397371",
    "flag_hr": "5291999676948569127", "flag_cu": "5291963947115631526",
    "flag_cy": "5294062721539526918", "flag_cz": "5294242852467923382",
    "flag_dk": "5294531860817268837", "flag_eg": "5293992082212409502",
    "flag_ee": "5291951143818123103", "flag_et": "5292245976143124155",
    "flag_fi": "5294049961191690629", "flag_fr": "5291817660529533837",
    "flag_ge": "5294349389131697267", "flag_de": "5292013274815028523",
    "flag_gh": "5294347396266873249", "flag_gr": "5291948395039054764",
    "flag_hu": "5294229581018975260", "flag_in": "5291933173674957761",
    "flag_ir": "5294220170745630736", "flag_iq": "5294325010897327367",
    "flag_ie": "5294471971793293647", "flag_il": "5294069056616289553",
    "flag_it": "5291826830284709120", "flag_jp": "5291799063321139445",
    "flag_jo": "5291988613112814801", "flag_kz": "5294227175837290463",
    "flag_ke": "5292111852904416801", "flag_kr": "5294408281723262763",
    "flag_kw": "5292066437920218075", "flag_kg": "5292091954320922577",
    "flag_lv": "5292236016113966127", "flag_lb": "5294193108156699621",
    "flag_ly": "5291858711826946840", "flag_lt": "5294343084119708700",
    "flag_lu": "5294423709245787718", "flag_my": "5291858351049696702",
    "flag_mx": "5294535073452809778", "flag_ma": "5292108962391414885",
    "flag_mm": "5294254478944393569", "flag_np": "5294458756178924088",
    "flag_nl": "5291917797692042265", "flag_nz": "5294189019347833274",
    "flag_ng": "5294456308047563965", "flag_no": "5291761718580502030",
    "flag_om": "5291813666209946812", "flag_pk": "5291825606219029010",
    "flag_ps": "5294289826525238172", "flag_pa": "5291959935616178405",
    "flag_ph": "5291798075478661634", "flag_pe": "5292099427564018941",
    "flag_pl": "5292190970496963836", "flag_pt": "5294436555492973610",
    "flag_qa": "5292166360334357676", "flag_ro": "5294107724206856227",
    "flag_ru": "5294335323113807278", "flag_sa": "5294163983983463099",
    "flag_sn": "5292087023698466689", "flag_rs": "5294458584380230360",
    "flag_sg": "5294451304410663668", "flag_sk": "5294538440707166931",
    "flag_si": "5294279359689938006", "flag_so": "5294058817414255960",
    "flag_za": "5294325281480266304", "flag_es": "5294513087515216901",
    "flag_lk": "5292102670264328257", "flag_sd": "5294177148058228060",
    "flag_se": "5291737091238026321", "flag_ch": "5291791748991835084",
    "flag_sy": "5294013428199869487", "flag_tw": "5294095745543069603",
    "flag_tj": "5294120269806328883", "flag_tz": "5292146096678658977",
    "flag_th": "5293994384314882755", "flag_tr": "5293993400767367408",
    "flag_tm": "5294098958178603764", "flag_ug": "5294192317882716626",
    "flag_ae": "5294314831824835370", "flag_gb": "5293993521026453119",
    "flag_ua": "5294263837678131580", "flag_us": "5294244076533600593",
    "flag_uz": "5294217645304864345", "flag_ve": "5294476442854247878",
    "flag_vn": "5294235963340379688", "flag_ye": "5294058972033076492",
    "flag_zm": "5294100109229838880", "flag_zw": "5294422158762592930",
    "flag_id": "5291933173674957761",
}

def ce(key: str, fallback: str = "●") -> str:
    eid = E.get(key, "")
    if not eid:
        return fallback
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'

# ════════════════════════════════════════════════════
#            COUNTRY / PHONE HELPERS
# ════════════════════════════════════════════════════
COUNTRY_PREFIXES = {
    "1": "US", "7": "RU", "20": "EG", "27": "ZA", "30": "GR", "31": "NL",
    "32": "BE", "33": "FR", "34": "ES", "36": "HU", "39": "IT", "40": "RO",
    "41": "CH", "43": "AT", "44": "GB", "45": "DK", "46": "SE", "47": "NO",
    "48": "PL", "49": "DE", "51": "PE", "52": "MX", "53": "CU", "54": "AR",
    "55": "BR", "56": "CL", "57": "CO", "58": "VE", "60": "MY", "61": "AU",
    "62": "ID", "63": "PH", "64": "NZ", "65": "SG", "66": "TH", "81": "JP",
    "82": "KR", "84": "VN", "86": "CN", "90": "TR", "91": "IN", "92": "PK",
    "93": "AF", "94": "LK", "95": "MM", "98": "IR", "212": "MA", "213": "DZ",
    "216": "TN", "218": "LY", "220": "GM", "221": "SN", "222": "MR",
    "223": "ML", "224": "GN", "225": "CI", "226": "BF", "227": "NE",
    "228": "TG", "229": "BJ", "230": "MU", "231": "LR", "232": "SL",
    "233": "GH", "234": "NG", "235": "TD", "236": "CF", "237": "CM",
    "238": "CV", "240": "GQ", "241": "GA", "242": "CG", "244": "AO",
    "249": "SD", "250": "RW", "251": "ET", "252": "SO", "253": "DJ",
    "254": "KE", "255": "TZ", "256": "UG", "257": "BI", "258": "MZ",
    "260": "ZM", "261": "MG", "263": "ZW", "264": "NA", "265": "MW",
    "266": "LS", "267": "BW", "268": "SZ", "291": "ER", "297": "AW",
    "350": "GI", "351": "PT", "352": "LU", "353": "IE", "354": "IS",
    "355": "AL", "356": "MT", "357": "CY", "358": "FI", "359": "BG",
    "370": "LT", "371": "LV", "372": "EE", "373": "MD", "374": "AM",
    "375": "BY", "376": "AD", "377": "MC", "378": "SM", "380": "UA",
    "381": "RS", "382": "ME", "385": "HR", "386": "SI", "387": "BA",
    "389": "MK", "420": "CZ", "421": "SK", "423": "LI", "501": "BZ",
    "502": "GT", "503": "SV", "504": "HN", "505": "NI", "506": "CR",
    "507": "PA", "509": "HT", "591": "BO", "592": "GY", "593": "EC",
    "595": "PY", "597": "SR", "598": "UY", "670": "TL", "673": "BN",
    "675": "PG", "676": "TO", "677": "SB", "678": "VU", "679": "FJ",
    "680": "PW", "682": "CK", "685": "WS", "686": "KI", "688": "TV",
    "691": "FM", "692": "MH", "850": "KP", "852": "HK", "853": "MO",
    "855": "KH", "856": "LA", "880": "BD", "886": "TW", "960": "MV",
    "961": "LB", "962": "JO", "963": "SY", "964": "IQ", "965": "KW",
    "966": "SA", "967": "YE", "968": "OM", "970": "PS", "971": "AE",
    "972": "IL", "973": "BH", "974": "QA", "975": "BT", "976": "MN",
    "977": "NP", "992": "TJ", "993": "TM", "994": "AZ", "995": "GE",
    "996": "KG", "998": "UZ",
}

COUNTRY_NAMES = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AD": "Andorra",
    "AO": "Angola", "AG": "Antigua & Barbuda", "AR": "Argentina", "AM": "Armenia",
    "AU": "Australia", "AT": "Austria", "AZ": "Azerbaijan", "BS": "Bahamas",
    "BH": "Bahrain", "BD": "Bangladesh", "BB": "Barbados", "BY": "Belarus",
    "BE": "Belgium", "BZ": "Belize", "BJ": "Benin", "BT": "Bhutan",
    "BO": "Bolivia", "BA": "Bosnia", "BW": "Botswana", "BR": "Brazil",
    "BN": "Brunei", "BG": "Bulgaria", "BF": "Burkina Faso", "BI": "Burundi",
    "KH": "Cambodia", "CM": "Cameroon", "CA": "Canada", "CV": "Cape Verde",
    "CF": "Central African Rep.", "TD": "Chad", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "KM": "Comoros", "CG": "Congo", "CR": "Costa Rica",
    "CI": "Côte d'Ivoire", "HR": "Croatia", "CU": "Cuba", "CY": "Cyprus",
    "CZ": "Czechia", "DK": "Denmark", "DJ": "Djibouti", "DM": "Dominica",
    "DO": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt",
    "SV": "El Salvador", "GQ": "Equatorial Guinea", "ER": "Eritrea",
    "EE": "Estonia", "ET": "Ethiopia", "FJ": "Fiji", "FI": "Finland",
    "FR": "France", "GA": "Gabon", "GM": "Gambia", "GE": "Georgia",
    "DE": "Germany", "GH": "Ghana", "GI": "Gibraltar", "GR": "Greece",
    "GL": "Greenland", "GT": "Guatemala", "GN": "Guinea", "GW": "Guinea-Bissau",
    "GY": "Guyana", "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong",
    "HU": "Hungary", "IS": "Iceland", "IN": "India", "ID": "Indonesia",
    "IR": "Iran", "IQ": "Iraq", "IE": "Ireland", "IL": "Israel", "IT": "Italy",
    "JM": "Jamaica", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan",
    "KE": "Kenya", "KI": "Kiribati", "KP": "North Korea", "KR": "South Korea",
    "KW": "Kuwait", "KG": "Kyrgyzstan", "LA": "Laos", "LV": "Latvia",
    "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya",
    "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macao",
    "MK": "N. Macedonia", "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia",
    "MV": "Maldives", "ML": "Mali", "MT": "Malta", "MH": "Marshall Islands",
    "MR": "Mauritania", "MU": "Mauritius", "MX": "Mexico", "FM": "Micronesia",
    "MD": "Moldova", "MC": "Monaco", "MN": "Mongolia", "ME": "Montenegro",
    "MA": "Morocco", "MZ": "Mozambique", "MM": "Myanmar", "NA": "Namibia",
    "NR": "Nauru", "NP": "Nepal", "NL": "Netherlands", "NZ": "New Zealand",
    "NI": "Nicaragua", "NE": "Niger", "NG": "Nigeria", "NU": "Niue",
    "NO": "Norway", "OM": "Oman", "PK": "Pakistan", "PW": "Palau",
    "PS": "Palestine", "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay",
    "PE": "Peru", "PH": "Philippines", "PL": "Poland", "PT": "Portugal",
    "PR": "Puerto Rico", "QA": "Qatar", "RO": "Romania", "RU": "Russia",
    "RW": "Rwanda", "SA": "Saudi Arabia", "SN": "Senegal", "RS": "Serbia",
    "SC": "Seychelles", "SL": "Sierra Leone", "SG": "Singapore", "SK": "Slovakia",
    "SI": "Slovenia", "SB": "Solomon Islands", "SO": "Somalia", "ZA": "South Africa",
    "ES": "Spain", "LK": "Sri Lanka", "SD": "Sudan", "SR": "Suriname",
    "SZ": "Swaziland", "SE": "Sweden", "CH": "Switzerland", "SY": "Syria",
    "TW": "Taiwan", "TJ": "Tajikistan", "TZ": "Tanzania", "TH": "Thailand",
    "TL": "Timor-Leste", "TG": "Togo", "TO": "Tonga", "TT": "Trinidad & Tobago",
    "TN": "Tunisia", "TR": "Turkey", "TM": "Turkmenistan", "TV": "Tuvalu",
    "UG": "Uganda", "UA": "Ukraine", "AE": "UAE", "GB": "United Kingdom",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan", "VU": "Vanuatu",
    "VE": "Venezuela", "VN": "Vietnam", "YE": "Yemen", "ZM": "Zambia", "ZW": "Zimbabwe",
}

def get_country_name(code: str) -> str:
    return COUNTRY_NAMES.get((code or "").upper(), code.upper() if code else "Unknown")

def get_flag_emoji(code: str) -> str:
    if not code or len(code) != 2:
        return ce("globe", "🌍")
    key = f"flag_{code.lower()}"
    if key in E:
        return f'<tg-emoji emoji-id="{E[key]}">🏳️</tg-emoji>'
    return "🌍"

def get_flag_icon_id(code: str) -> str:
    if not code or len(code) != 2:
        return E.get("globe", "5447410659077661506")
    key = f"flag_{code.lower()}"
    return E.get(key, E.get("globe", "5447410659077661506"))

def get_country_from_phone(phone: str) -> tuple:
    digits = re.sub(r"\D", "", str(phone))
    for length in range(min(6, len(digits)), 0, -1):
        prefix = digits[:length]
        if prefix in COUNTRY_PREFIXES:
            code = COUNTRY_PREFIXES[prefix]
            return code, get_flag_emoji(code)
    return "", ""

# ════════════════════════════════════════════════════
#              HELPER / UTILITY FUNCTIONS
# ════════════════════════════════════════════════════
def is_admin(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (str(user_id),))
    return cursor.fetchone() is not None

def is_banned(user_id: int) -> bool:
    row = cursor.execute("SELECT is_banned FROM users WHERE id=?", (user_id,)).fetchone()
    return bool(row and row[0] == 1)

def is_maintenance_mode() -> bool:
    row = cursor.execute("SELECT value FROM config WHERE key='maintenance_mode'").fetchone()
    return bool(row and row[0] == "on")

async def check_maintenance(user_id: int, message=None, callback=None) -> bool:
    if is_banned(user_id):
        text = f'{ce("ban","🚫")} <b>You are banned.</b> Contact Admin.'
        if callback:
            await callback.answer("You are banned.", show_alert=True)
            await safe_edit(callback.message, text)
        elif message:
            await safe_send(message, text)
        return True
    if is_maintenance_mode() and not is_admin(user_id):
        text = f'{ce("maintenance","🔧")} <b>Bot is under maintenance.</b> Please try again later.'
        if callback:
            await callback.answer("Maintenance mode is ON", show_alert=True)
            await safe_edit(callback.message, text)
        elif message:
            await safe_send(message, text)
        return True
    return False

def strip_html(text: str) -> str:
    text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text)
    return re.sub(r'<[^>]+>', '', text)

async def safe_send(target, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        if isinstance(target, types.Message):
            return await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif hasattr(target, "answer"):
            return await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            return await target.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        if isinstance(target, types.Message):
            return await target.answer(strip_html(text), reply_markup=reply_markup)
        elif hasattr(target, "answer"):
            return await target.answer(strip_html(text), reply_markup=reply_markup)
        else:
            return await target.message.answer(strip_html(text), reply_markup=reply_markup)

async def safe_edit(msg, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        return await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        return await msg.edit_text(strip_html(text), reply_markup=reply_markup)

def get_user_balance(user_id: int) -> float:
    row = cursor.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
    return float(row[0]) if row else 0.0

def deduct_balance(user_id: int, amount: float) -> bool:
    """Return True if successful, False if insufficient."""
    if amount <= 0:
        return True
    bal = get_user_balance(user_id)
    if bal < amount:
        return False
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, user_id))
    db.commit()
    return True

# ════════════════════════════════════════════════════
#                   OTP EXTRACTION
# ════════════════════════════════════════════════════
user_processed_otps: deque = deque(maxlen=5000)
active_manual_pollers: dict = {}

def extract_otp(message) -> str | None:
    if not message:
        return None
    s = str(message).strip().upper()
    if s in {"0", "00", "000", "0000", "000000", "NULL", "NONE", "WAITING", "PENDING", ""}:
        return None
    m = re.search(r'(?i)(?:WHATSAPP|WA|CODE|TELEGRAM|TG).*?(\d{3})[- ]?(\d{3})', s)
    if m:
        return m.group(1) + m.group(2)
    m = re.search(r'(?<!\d)(\d{3,4})[\s\-](\d{3,4})(?!\d)', s)
    if m:
        return m.group(1) + m.group(2)
    matches = re.findall(r'(?<!\d)(\d{4,8})(?!\d)', s)
    for match in matches:
        if not re.match(r'^0+$', match):
            return match
    numbers = re.findall(r'\d{4,8}', s.replace(" ", "").replace("-", ""))
    for match in numbers:
        if not re.match(r'^0+$', match):
            return match[:8]
    return None

# ════════════════════════════════════════════════════
#               DATABASE BACKUP / RESTORE
# ════════════════════════════════════════════════════
def create_db_backup() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{ts}.db")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    src.backup(dst)
    dst.close()
    src.close()
    return backup_path

def restore_db_from_file(file_path: str) -> bool:
    try:
        test_conn = sqlite3.connect(file_path)
        test_cur = test_conn.cursor()
        test_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in test_cur.fetchall()]
        test_conn.close()
        if not tables:
            return False
        src = sqlite3.connect(file_path)
        dst = sqlite3.connect(DB_PATH)
        src.backup(dst)
        dst.close()
        src.close()
        return True
    except Exception as e:
        logger.error(f"DB restore error: {e}")
        return False

def list_backups() -> list:
    result = []
    if not os.path.isdir(BACKUP_DIR):
        return result
    for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if fname.endswith(".db"):
            fpath = os.path.join(BACKUP_DIR, fname)
            size_kb = os.path.getsize(fpath) // 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d %b %Y %H:%M")
            result.append((fname, fpath, size_kb, mtime))
    return result

# ════════════════════════════════════════════════════
#                 LAMIX SMS API
# ════════════════════════════════════════════════════
http_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

async def fetch_lamix_messages(limit: int = 100) -> list:
    session = await get_session()
    headers = {
        "Authorization": f"Bearer {LAMIX_API_TOKEN}",
        "Accept": "application/json",
    }
    try:
        async with session.get(
            f"{LAMIX_BASE_URL}/api/v1/messages",
            headers=headers,
            params={"limit": limit},
            timeout=aiohttp.ClientTimeout(total=20),
            ssl=False,
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                records = data.get("records", [])
                return records if isinstance(records, list) else []
            elif resp.status == 429:
                retry = resp.headers.get("Retry-After", "5")
                logger.warning(f"Lamix rate limited, retry after {retry}s")
                try:
                    await asyncio.sleep(int(retry))
                except Exception:
                    await asyncio.sleep(5)
                return []
            elif resp.status in (401, 403):
                logger.error(f"Lamix auth error {resp.status}: check API token")
                return []
            else:
                logger.error(f"Lamix HTTP {resp.status}")
    except Exception as e:
        logger.error(f"Lamix fetch error: {e}")
    return []

def extract_lamix_record_info(rec: dict) -> tuple:
    number = rec.get("number") or ""
    cli = rec.get("cli") or ""
    content = rec.get("content") or ""
    timestamp = rec.get("time") or ""
    return (str(number), str(cli), str(content), timestamp)

# ════════════════════════════════════════════════════
#              OTP REWARD / NOTIFICATION
# ════════════════════════════════════════════════════
async def process_otp_reward(
    user_id: int,
    phone: str,
    otp: str,
    service_name: str = "New FB",
):
    unique_key = f"{phone}_{otp}"
    if unique_key in user_processed_otps:
        return
    user_processed_otps.append(unique_key)

    try:
        cursor.execute(
            "INSERT INTO otp_success_logs (user_id, phone_number, otp_code, timestamp, service_name) VALUES (?,?,?,?,?)",
            (user_id, phone, otp, datetime.now().isoformat(), service_name),
        )
        db.commit()
    except Exception as e:
        logger.error(f"DB log error: {e}")

    country_code, flag_emoji = get_country_from_phone(phone)
    if not country_code:
        country_code = "GLOBAL"
        country_name = "Global"
        flag_emoji = ce("globe", "🌍")
    else:
        country_name = get_country_name(country_code)

    svc_up = service_name.upper()
    SVC_MAP = {
        "NEW FB": ("New FB", "facebook"),
        "WHATSAPP": ("WhatsApp", "whatsapp"),
        "INSTAGRAM": ("Instagram", "instagram"),
        "FACEBOOK": ("Facebook", "facebook"),
        "TELEGRAM": ("Telegram", "telegram"),
        "TG": ("Telegram", "telegram"),
    }
    display_svc, svc_key = SVC_MAP.get(svc_up, (service_name.title(), "facebook"))

    text = (
        f"╔══════ {ce('success','✅')} <b>OTP Received</b> ══════╗\n"
        f"║ {ce('globe','🌐')} {flag_emoji} <b>{country_name}</b>\n"
        f"║ {ce(svc_key,'📘')} <b>{display_svc}</b>\n"
        f"║ {ce('phone','📞')} <code>{phone}</code>\n"
        f"║ {ce('lock','🔑')} <code>{otp}</code>\n"
        f"╚═══════════════════════╝"
    )

    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"OTP send error user {user_id}: {e}")
        try:
            await bot.send_message(user_id, strip_html(text))
        except Exception:
            pass

    channel_row = cursor.execute("SELECT value FROM config WHERE key='otp_channel_id'").fetchone()
    if channel_row:
        try:
            await bot.send_message(int(channel_row[0]), text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Channel forward error: {e}")

# ════════════════════════════════════════════════════
#            MANUAL OTP POLLER
# ════════════════════════════════════════════════════
async def poll_manual_otp(user_id: int, phone_number: str, service_name: str, start_time: float):
    end_time = start_time + 1200
    clean_phone = re.sub(r"\D", "", phone_number)
    seen_otps: set = set()

    while time.time() < end_time:
        row = cursor.execute("SELECT active_manual FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not row[0]:
            break
        res = cursor.execute(
            "SELECT otp_code FROM otp_success_logs WHERE user_id=? AND phone_number=? AND julianday(timestamp) >= julianday(?) ORDER BY timestamp DESC LIMIT 1",
            (user_id, clean_phone, datetime.fromtimestamp(start_time).isoformat()),
        ).fetchone()
        if res and res[0] and res[0] not in seen_otps:
            seen_otps.add(res[0])
            await process_otp_reward(user_id, clean_phone, res[0], service_name=service_name)
            return
        try:
            messages = await fetch_lamix_messages(limit=100)
            for rec in messages:
                num, cli, content, _ = extract_lamix_record_info(rec)
                clean_num = re.sub(r"\D", "", str(num))
                if clean_num and (clean_phone == clean_num or clean_phone in clean_num or clean_num in clean_phone):
                    otp = extract_otp(content)
                    if otp and otp not in seen_otps:
                        seen_otps.add(otp)
                        await process_otp_reward(user_id, clean_phone, otp, service_name=service_name)
                        return
        except Exception as e:
            logger.error(f"Manual poll error: {e}")
        await asyncio.sleep(3)

    if user_id in active_manual_pollers:
        active_manual_pollers[user_id] = [t for t in active_manual_pollers[user_id] if not t.done()]

async def process_manual_expiry():
    while True:
        try:
            now = time.time()
            rows = cursor.execute("SELECT id, active_manual FROM users WHERE active_manual IS NOT NULL").fetchall()
            for user_id, active_raw in rows:
                if not active_raw:
                    continue
                active = json.loads(active_raw)
                if now - active.get("buy_time", 0) > 1200:
                    nums = active.get("nums", [])
                    svc_id = active.get("svc_id")
                    cursor.execute("UPDATE users SET active_manual=NULL WHERE id=?", (user_id,))
                    if svc_id:
                        for num in nums:
                            cursor.execute("INSERT INTO manual_numbers (service_id, number) VALUES (?,?)", (svc_id, num))
                        cursor.execute("UPDATE manual_services SET stock = (SELECT COUNT(*) FROM manual_numbers WHERE service_id=?) WHERE id=?", (svc_id, svc_id))
                    db.commit()
                    if user_id in active_manual_pollers:
                        for task in active_manual_pollers[user_id]:
                            task.cancel()
                        del active_manual_pollers[user_id]
                    try:
                        await bot.send_message(
                            user_id,
                            f'{ce("warning","⚠️")} আপনার ম্যানুয়াল নাম্বারের মেয়াদ শেষ হয়েছে।',
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Expiry check error: {e}")
        await asyncio.sleep(60)

# ════════════════════════════════════════════════════
#              KEYBOARDS / MENUS
# ════════════════════════════════════════════════════
def main_menu(user_id: int) -> types.ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(
        types.KeyboardButton(text="GET NUMBER", icon_custom_emoji_id=E["phone"]),
        types.KeyboardButton(text="GET 2FA",    icon_custom_emoji_id=E["lock"]),
    )
    b.row(
        types.KeyboardButton(text="EXTRACT OTP", icon_custom_emoji_id=E["folder"]),
        types.KeyboardButton(text="STATUS",       icon_custom_emoji_id=E["chart"]),
    )
    b.row(
        types.KeyboardButton(text="MY BALANCE", icon_custom_emoji_id=E["money"]),
    )
    if is_admin(user_id):
        b.row(types.KeyboardButton(text="ADMIN PANEL", icon_custom_emoji_id=E["gear"]))
    return b.as_markup(resize_keyboard=True)

def get_number_menu() -> types.InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Facebook",  callback_data="view_svc_FACEBOOK",  icon_custom_emoji_id=E["facebook"]),
        InlineKeyboardButton(text="WhatsApp",  callback_data="view_svc_WHATSAPP",  icon_custom_emoji_id=E["whatsapp"]),
    )
    b.row(
        InlineKeyboardButton(text="Instagram", callback_data="view_svc_INSTAGRAM", icon_custom_emoji_id=E["instagram"]),
        InlineKeyboardButton(text="Telegram",  callback_data="view_svc_TELEGRAM",  icon_custom_emoji_id=E["telegram"]),
    )
    b.row(
        InlineKeyboardButton(text="New FB",    callback_data="view_svc_NEW FB",    icon_custom_emoji_id=E["facebook"]),
    )
    return b.as_markup()

def admin_menu() -> types.InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📁 Add Manual Numbers",   callback_data="add_manual_numbers",    icon_custom_emoji_id=E["add"])
    b.button(text="🗂 Manage Services",      callback_data="manage_manual_numbers", icon_custom_emoji_id=E["folder"])
    b.button(text="👥 Manage Admins",        callback_data="manage_admins",          icon_custom_emoji_id=E["users"])
    b.button(text="📊 Live Stats",           callback_data="admin_stats",            icon_custom_emoji_id=E["chart"])
    b.button(text="👤 Total Users",          callback_data="total_users",            icon_custom_emoji_id=E["users"])
    b.button(text="🔍 Search User",          callback_data="search_user",            icon_custom_emoji_id=E["search"])
    b.button(text="💰 Add Balance",          callback_data="add_balance",            icon_custom_emoji_id=E["money"])
    b.button(text="📡 Set OTP Channel",      callback_data="set_otp_channel",        icon_custom_emoji_id=E["signal"])
    b.button(text="🏆 Top 10 Users",         callback_data="top_10_users",           icon_custom_emoji_id=E["trophy"])
    b.button(text="📣 Broadcast",            callback_data="admin_bc",               icon_custom_emoji_id=E["broadcast"])
    b.button(text="🚫 Ban User",             callback_data="ban_user_btn",           icon_custom_emoji_id=E["ban"])
    b.button(text="✅ Unban User",           callback_data="unban_user_btn",         icon_custom_emoji_id=E["success"])
    b.button(text="💾 DB Backup",            callback_data="db_backup",              icon_custom_emoji_id=E["backup"])
    b.button(text="♻️ DB Restore",           callback_data="db_restore_list",        icon_custom_emoji_id=E["restore"])
    current_m = "ON" if is_maintenance_mode() else "OFF"
    b.button(text=f"🔧 Maintenance [{current_m}]", callback_data="toggle_maintenance", icon_custom_emoji_id=E["maintenance"])
    b.adjust(2)
    return b.as_markup()

def admin_back_btn() -> types.InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Back", callback_data="admin_back", icon_custom_emoji_id=E["back"]))
    return b.as_markup()

# ════════════════════════════════════════════════════
#                   FSM STATES
# ════════════════════════════════════════════════════
class AdminStates(StatesGroup):
    waiting_broadcast       = State()
    waiting_add_admin       = State()
    waiting_remove_admin    = State()
    waiting_manual_file     = State()
    waiting_manual_svc_name = State()
    waiting_manual_country  = State()
    waiting_manual_give     = State()
    waiting_manual_price    = State()
    waiting_manual_cooldown = State()
    waiting_search_user     = State()
    waiting_otp_channel     = State()
    waiting_ban_user        = State()
    waiting_unban_user      = State()
    waiting_db_restore_file = State()
    waiting_add_balance     = State()
    waiting_edit_price      = State()

class UserStates(StatesGroup):
    waiting_for_2fa = State()

# ════════════════════════════════════════════════════
#                  ERROR HANDLER
# ════════════════════════════════════════════════════
@dp.errors()
async def global_error_handler(update, exception):
    logger.error(f"Unhandled exception: {exception}", exc_info=True)
    try:
        if update and hasattr(update, "message") and update.message:
            await update.message.answer(f'{ce("warning","⚠️")} একটি ত্রুটি ঘটেছে, দয়া করে আবার চেষ্টা করুন।', parse_mode="HTML")
    except Exception:
        pass
    return True

# ════════════════════════════════════════════════════
#                START / HOME
# ════════════════════════════════════════════════════
HOME_TEXT = """
{planet}  <b><u>𝗦𝗞𝗬 𝗢𝗧𝗣 𝗣𝗥𝗢</u></b>
━━━━━━━━━━━━━━━━━━━━━━

👋 𝗛𝗘𝗟𝗟𝗢, <b>{name}</b>!

Get OTP codes instantly using virtual phone numbers
— fast, reliable, and global.

⚡ <b>Instant Delivery</b>
{globe} <b>Global Numbers</b>
{cat} <b>Auto OTP Detection</b>

━━━━━━━━━━━━━━━━━━━━━━
{channel} <b>Channel:</b> @FBDEALZONEBUYSELL
{chat} <b>Group:</b> @SKYOTP_SKY
━━━━━━━━━━━━━━━━━━━━━━
{shop} <b>Use the menu buttons below ↓</b>
"""

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, username, fullname, join_date) VALUES (?,?,?,?)",
        (message.from_user.id, message.from_user.username, message.from_user.full_name, datetime.now().isoformat()),
    )
    db.commit()
    if await check_maintenance(message.from_user.id, message=message):
        return
    text = HOME_TEXT.format(
        planet=ce("planet","🪐"), globe=ce("globe","🌐"),
        cat=ce("cat","🐱"), channel=ce("channel","📣"),
        chat=ce("chat","💬"), shop=ce("shopping","🛍️"),
        name=message.from_user.first_name,
    )
    await message.answer(text, reply_markup=main_menu(message.from_user.id), parse_mode="HTML")

async def send_home_view(callback: types.CallbackQuery):
    text = HOME_TEXT.format(
        planet=ce("planet","🪐"), globe=ce("globe","🌐"),
        cat=ce("cat","🐱"), channel=ce("channel","📣"),
        chat=ce("chat","💬"), shop=ce("shopping","🛍️"),
        name=callback.from_user.first_name,
    )
    await safe_edit(callback.message, text, reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(F.data.in_({"back_to_main", "back_to_get_number", "back_to_home", "back_to_services_menu"}))
async def back_handlers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_home_view(callback)
    await callback.answer()

# ════════════════════════════════════════════════════
#              MY BALANCE
# ════════════════════════════════════════════════════
@dp.message(F.text == "MY BALANCE")
async def my_balance(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_maintenance(message.from_user.id, message=message):
        return
    bal = get_user_balance(message.from_user.id)
    text = (
        f"{ce('money','💰')} <b>Your Balance</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('card','💳')} <b>Amount:</b> <code>{bal:.2f}</code> ৳\n\n"
        f"{ce('info','💡')} <i>Contact admin to top up.</i>"
    )
    await safe_send(message, text)

# ════════════════════════════════════════════════════
#              GET NUMBER FLOW
# ════════════════════════════════════════════════════
@dp.message(F.text == "GET NUMBER")
async def get_number_selection(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_maintenance(message.from_user.id, message=message):
        return
    text = (
        f"{ce('success','✅')} <b>Select a Service</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('facebook','📘')} Facebook  ·  {ce('whatsapp','💬')} WhatsApp\n"
        f"{ce('instagram','📸')} Instagram ·  {ce('telegram','✈️')} Telegram\n"
        f"{ce('facebook','📘')} New FB\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('shopping','🛍️')} <i>Tap your desired service below</i>"
    )
    await safe_send(message, text, reply_markup=get_number_menu())

@dp.callback_query(F.data.startswith("view_svc_"))
async def view_service_countries(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    svc_name = callback.data[9:]
    manuals = cursor.execute(
        "SELECT id, country_name, flag, stock, price FROM manual_services WHERE service_name=? AND stock > 0",
        (svc_name.upper(),),
    ).fetchall()

    now_str = datetime.now().strftime("%I:%M:%S %p")
    text = (
        f"{ce('globe','🌐')} <b>{svc_name.upper()}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('red_circle','🔴')} 𝗟𝗜𝗩𝗘: <b>Available Countries</b>\n\n"
        f"{ce('shopping','🛍️')} <i>Select a country to get a number</i>\n"
        f"{ce('refresh','🔄')} <i>Updated: {now_str}</i>"
    )
    b = InlineKeyboardBuilder()
    for svc_id, c_name, flag, stock, price in manuals:
        price_str = "🆓 Free" if price <= 0 else f"💰 {price:.2f}৳"
        b.row(InlineKeyboardButton(
            text=f"{c_name} — {stock} left · {price_str}",
            callback_data=f"man_cntry_{svc_id}",
            icon_custom_emoji_id=E["package"],
        ))
    if not manuals:
        b.row(InlineKeyboardButton(text="⚠️ No countries available", callback_data="none", icon_custom_emoji_id=E["ban"]))
    b.row(
        InlineKeyboardButton(text="🔄 Refresh",  callback_data=f"view_svc_{svc_name}",      icon_custom_emoji_id=E["refresh"]),
        InlineKeyboardButton(text="◀️ Back",      callback_data="back_to_services_menu",     icon_custom_emoji_id=E["back"]),
    )
    try:
        await safe_edit(callback.message, text, reply_markup=b.as_markup())
    except Exception:
        await safe_send(callback.message, text, reply_markup=b.as_markup())
    await callback.answer("Refreshed!")

# ════════════════════════════════════════════════════
#           MANUAL COUNTRY SELECTION (Paid)
# ════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("man_cntry_"))
async def manual_country_selected(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if await check_maintenance(callback.from_user.id, callback=callback):
        return
    svc_id = int(callback.data[10:])
    uid = callback.from_user.id
    wait_msg = await safe_edit(callback.message, f"{ce('waiting','⏳')} <b>Fetching numbers...</b>")

    row = cursor.execute(
        "SELECT service_name, country_name, give_amount, stock, flag, cooldown, price FROM manual_services WHERE id=? AND stock > 0",
        (svc_id,),
    ).fetchone()
    if not row:
        await safe_edit(wait_msg, f"{ce('error','❌')} Service not available or out of stock.")
        return
    svc_name, c_name, give_amount, stock, flag, cooldown, price = row

    # ── Cooldown ──
    user_cd_raw = cursor.execute("SELECT manual_cooldowns FROM users WHERE id=?", (uid,)).fetchone()
    user_cds = json.loads(user_cd_raw[0]) if user_cd_raw and user_cd_raw[0] else {}
    last_time = user_cds.get(str(svc_id), 0)
    if time.time() - last_time < cooldown:
        wait_sec = int(cooldown - (time.time() - last_time))
        await safe_edit(wait_msg, f"{ce('waiting','⏳')} Please wait <b>{wait_sec}s</b> before getting another number.")
        return

    # ── Paid check: প্রতি নাম্বারের দাম × give_amount ──
    total_cost = price * give_amount
    if total_cost > 0:
        bal = get_user_balance(uid)
        if bal < total_cost:
            await safe_edit(
                wait_msg,
                f"{ce('error','❌')} <b>Insufficient balance!</b>\n\n"
                f"{ce('money','💰')} Required: <code>{total_cost:.2f}</code> ৳\n"
                f"{ce('card','💳')} Your balance: <code>{bal:.2f}</code> ৳\n\n"
                f"<i>Contact admin to top up.</i>",
            )
            return

    # ── Numbers নাও ──
    nums_rows = cursor.execute(
        "SELECT number FROM manual_numbers WHERE service_id=? ORDER BY RANDOM() LIMIT ?",
        (svc_id, give_amount),
    ).fetchall()
    nums = [r[0] for r in nums_rows]
    if len(nums) < give_amount:
        await safe_edit(wait_msg, f"{ce('error','❌')} Not enough numbers in stock.")
        return

    # ── Balance কাটো (paid হলে) ──
    if total_cost > 0:
        if not deduct_balance(uid, total_cost):
            await safe_edit(wait_msg, f"{ce('error','❌')} Payment failed. Try again.")
            return

    cursor.execute(
        "DELETE FROM manual_numbers WHERE service_id=? AND number IN ({})".format(",".join("?" * len(nums))),
        (svc_id, *nums),
    )
    cursor.execute(
        "UPDATE manual_services SET stock = (SELECT COUNT(*) FROM manual_numbers WHERE service_id=?) WHERE id=?",
        (svc_id, svc_id),
    )
    active_data = json.dumps({"svc_id": svc_id, "svc": svc_name, "c": c_name, "nums": nums, "buy_time": time.time()})
    user_cds[str(svc_id)] = time.time()
    cursor.execute("UPDATE users SET active_manual=?, manual_cooldowns=? WHERE id=?", (active_data, json.dumps(user_cds), uid))
    db.commit()

    if uid in active_manual_pollers:
        for t in active_manual_pollers[uid]:
            t.cancel()
        active_manual_pollers[uid] = []
    start_time = time.time()
    active_manual_pollers[uid] = [asyncio.create_task(poll_manual_otp(uid, num, svc_name, start_time)) for num in nums]

    SVC_ICONS = {"FACEBOOK": E["facebook"], "WHATSAPP": E["whatsapp"], "INSTAGRAM": E["instagram"], "NEW FB": E["facebook"], "TELEGRAM": E["telegram"]}
    icon_id = SVC_ICONS.get(svc_name.upper(), E["phone"])

    remaining = cursor.execute("SELECT COUNT(*) FROM manual_numbers WHERE service_id=?", (svc_id,)).fetchone()[0]
    text = (
        f"╔══════ {ce('globe','🌐')} <b>Number Ready</b> ══════╗\n"
        f"║ {flag} <b>{c_name}</b>\n"
        f"║ 📦 Stock: <b>{remaining}</b> remaining\n"
        f"║ {ce('waiting','⏳')} <i>Waiting for OTP...</i>\n"
        f"╚══════════════════════════╝"
    )
    b = InlineKeyboardBuilder()
    for num in nums:
        num_clean = re.sub(r"^\+", "", str(num))
        b.row(
            InlineKeyboardButton(
                text=f"📋 +{num_clean}",
                copy_text=CopyTextButton(text=f"+{num_clean}"),
                icon_custom_emoji_id=icon_id,
            ),
            InlineKeyboardButton(
                text=f"🔢 {num_clean}",
                copy_text=CopyTextButton(text=num_clean),
                icon_custom_emoji_id=E["phone"],
            ),
        )
    b.row(InlineKeyboardButton(text="🔄 Change Number",  callback_data=f"man_change_{svc_id}", icon_custom_emoji_id=E["next"]))
    b.row(InlineKeyboardButton(text="🌐 Change Country", callback_data=f"view_svc_{svc_name}", icon_custom_emoji_id=E["globe"]))
    b.row(
        InlineKeyboardButton(text="🏠 Home",      callback_data="back_to_home", icon_custom_emoji_id=E["store"]),
        InlineKeyboardButton(text="💬 OTP Group", url=OTP_GROUP_LINK,           icon_custom_emoji_id=E["chat"]),
    )
    await safe_edit(wait_msg, text, reply_markup=b.as_markup())
    await callback.answer()

# ════════════════════════════════════════════════════
#    Change Number — paid-aware ফিক্স
# ════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("man_change_"))
async def man_change_numbers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if await check_maintenance(callback.from_user.id, callback=callback):
        return

    svc_id = int(callback.data.split("_")[-1])
    uid = callback.from_user.id

    active_row = cursor.execute("SELECT active_manual FROM users WHERE id=?", (uid,)).fetchone()
    if not active_row or not active_row[0]:
        await callback.answer("No active manual numbers.", show_alert=True)
        return
    active = json.loads(active_row[0])
    if active.get("svc_id") != svc_id:
        await callback.answer("Service mismatch.", show_alert=True)
        return

    svc_row = cursor.execute(
        "SELECT service_name, country_name, give_amount, flag, cooldown, price FROM manual_services WHERE id=?",
        (svc_id,),
    ).fetchone()
    if not svc_row:
        await callback.answer("Service not found.", show_alert=True)
        return
    svc_name, c_name, give_amount, flag, cooldown, price = svc_row

    # ── Cooldown ──
    user_cd_raw = cursor.execute("SELECT manual_cooldowns FROM users WHERE id=?", (uid,)).fetchone()
    user_cds = json.loads(user_cd_raw[0]) if user_cd_raw and user_cd_raw[0] else {}
    elapsed = time.time() - user_cds.get(str(svc_id), 0)
    if elapsed < cooldown:
        await callback.answer(f"Please wait {int(cooldown - elapsed)}s before changing.", show_alert=True)
        return

    # ── Paid check ──
    total_cost = price * give_amount
    if total_cost > 0:
        bal = get_user_balance(uid)
        if bal < total_cost:
            await callback.answer(f"Insufficient balance! Need {total_cost:.2f}৳", show_alert=True)
            return

    wait_msg = await safe_edit(callback.message, f"{ce('waiting','⏳')} <b>Fetching new numbers...</b>")

    # ── Step 1: পুরানো নাম্বার ফেরত দাও (normalize) ──
    old_nums_raw = active.get("nums", [])
    old_nums_norm = set()
    for n in old_nums_raw:
        clean = re.sub(r"\D", "", str(n))
        if clean:
            old_nums_norm.add(clean)

    for clean_num in old_nums_norm:
        cursor.execute(
            "INSERT OR IGNORE INTO manual_numbers (service_id, number) VALUES (?,?)",
            (svc_id, clean_num),
        )
    cursor.execute(
        "UPDATE manual_services SET stock = (SELECT COUNT(*) FROM manual_numbers WHERE service_id=?) WHERE id=?",
        (svc_id, svc_id),
    )
    db.commit()

    # ── Step 2: নতুন নাম্বার select (পুরানো বাদ) ──
    if old_nums_norm:
        all_rows = cursor.execute(
            "SELECT id, number FROM manual_numbers WHERE service_id=? ORDER BY RANDOM()",
            (svc_id,),
        ).fetchall()
        candidate_rows = []
        for row_id, num_str in all_rows:
            clean = re.sub(r"\D", "", str(num_str))
            if clean and clean not in old_nums_norm:
                candidate_rows.append((row_id, num_str))
                if len(candidate_rows) >= give_amount:
                    break
        new_nums = [num_str for _, num_str in candidate_rows]
    else:
        rows = cursor.execute(
            "SELECT number FROM manual_numbers WHERE service_id=? ORDER BY RANDOM() LIMIT ?",
            (svc_id, give_amount),
        ).fetchall()
        new_nums = [r[0] for r in rows]

    if len(new_nums) < give_amount:
        if new_nums:
            cursor.execute(
                "DELETE FROM manual_numbers WHERE service_id=? AND number IN ({})".format(",".join("?" * len(new_nums))),
                (svc_id, *new_nums),
            )
            cursor.execute(
                "UPDATE manual_services SET stock = (SELECT COUNT(*) FROM manual_numbers WHERE service_id=?) WHERE id=?",
                (svc_id, svc_id),
            )
        else:
            await safe_edit(
                wait_msg,
                f"{ce('error','❌')} <b>Stock শেষ!</b> এই service-এ আর নতুন নাম্বার নেই।",
            )
            cursor.execute("UPDATE users SET active_manual=NULL WHERE id=?", (uid,))
            db.commit()
            if uid in active_manual_pollers:
                for t in active_manual_pollers[uid]:
                    t.cancel()
                del active_manual_pollers[uid]
            return

    # ── Step 3: Balance কাটো ──
    if total_cost > 0:
        if not deduct_balance(uid, total_cost):
            await safe_edit(wait_msg, f"{ce('error','❌')} Payment failed. Try again.")
            return

    # ── Step 4: নতুন নাম্বার DB থেকে তুলে নাও ──
    placeholders = ",".join(["?"] * len(new_nums))
    cursor.execute(
        f"DELETE FROM manual_numbers WHERE service_id=? AND number IN ({placeholders})",
        (svc_id, *new_nums),
    )
    cursor.execute(
        "UPDATE manual_services SET stock = (SELECT COUNT(*) FROM manual_numbers WHERE service_id=?) WHERE id=?",
        (svc_id, svc_id),
    )

    active["nums"] = new_nums
    active["buy_time"] = time.time()
    user_cds[str(svc_id)] = time.time()
    cursor.execute(
        "UPDATE users SET active_manual=?, manual_cooldowns=? WHERE id=?",
        (json.dumps(active), json.dumps(user_cds), uid),
    )
    db.commit()

    if uid in active_manual_pollers:
        for t in active_manual_pollers[uid]:
            t.cancel()
    start_time = time.time()
    active_manual_pollers[uid] = [
        asyncio.create_task(poll_manual_otp(uid, num, svc_name, start_time)) for num in new_nums
    ]

    SVC_ICONS = {"FACEBOOK": E["facebook"], "WHATSAPP": E["whatsapp"], "INSTAGRAM": E["instagram"], "NEW FB": E["facebook"], "TELEGRAM": E["telegram"]}
    icon_id = SVC_ICONS.get(svc_name.upper(), E["phone"])

    remaining = cursor.execute("SELECT COUNT(*) FROM manual_numbers WHERE service_id=?", (svc_id,)).fetchone()[0]
    text = (
        f"╔══════ {ce('globe','🌐')} <b>Number Ready</b> ══════╗\n"
        f"║ {flag} <b>{c_name}</b>\n"
        f"║ 📦 Stock: <b>{remaining}</b> remaining\n"
        f"║ {ce('waiting','⏳')} <i>Waiting for OTP...</i>\n"
        f"╚══════════════════════════╝"
    )
    b = InlineKeyboardBuilder()
    for num in new_nums:
        num_clean = re.sub(r"^\+", "", str(num))
        b.row(
            InlineKeyboardButton(text=f"📋 +{num_clean}", copy_text=CopyTextButton(text=f"+{num_clean}"), icon_custom_emoji_id=icon_id),
            InlineKeyboardButton(text=f"🔢 {num_clean}",  copy_text=CopyTextButton(text=num_clean),       icon_custom_emoji_id=E["phone"]),
        )
    b.row(InlineKeyboardButton(text="🔄 Change Number",  callback_data=f"man_change_{svc_id}", icon_custom_emoji_id=E["next"]))
    b.row(InlineKeyboardButton(text="🌐 Change Country", callback_data=f"view_svc_{svc_name}", icon_custom_emoji_id=E["globe"]))
    b.row(
        InlineKeyboardButton(text="🏠 Home",      callback_data="back_to_home", icon_custom_emoji_id=E["store"]),
        InlineKeyboardButton(text="💬 OTP Group", url=OTP_GROUP_LINK,           icon_custom_emoji_id=E["chat"]),
    )
    await safe_edit(wait_msg, text, reply_markup=b.as_markup())
    await callback.answer("✅ নাম্বার পরিবর্তন হয়েছে!")

# ════════════════════════════════════════════════════
#                GET 2FA
# ════════════════════════════════════════════════════
@dp.message(F.text == "GET 2FA")
async def get_2fa_prompt(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_maintenance(message.from_user.id, message=message):
        return
    text = (
        f"{ce('cat','🐱')}{ce('lock','🔑')} <b>Get 2FA OTP</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{ce('cat','🐱')} Paste your <b>2FA Secret Key</b> below.\n\n"
        f"{ce('waiting','⏳')} <i>Example: JBSWY3DPEHPK3PXP</i>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{ce('info','💡')} <i>You will get a live 6-digit OTP.</i>"
    )
    await safe_send(message, text)
    await state.set_state(UserStates.waiting_for_2fa)

@dp.message(UserStates.waiting_for_2fa)
async def process_2fa(message: types.Message, state: FSMContext):
    secret = message.text.strip().replace(" ", "").upper()
    try:
        totp = pyotp.TOTP(secret)
        current_otp = totp.now()
    except Exception:
        await safe_send(message, f"{ce('error','❌')} <b>Invalid Secret Key!</b> Please provide a valid 2FA key.")
        return
    await state.clear()
    sent_msg = await safe_send(
        message,
        f"{ce('success','✅')} <b>Your 2FA Code:</b> <code>{current_otp}</code>\n\n"
        f"{ce('waiting','⏳')} <i>(Live updating every 30 seconds...)</i>",
    )
    asyncio.create_task(update_2fa_message(sent_msg, secret))

async def update_2fa_message(message: types.Message, secret: str):
    totp = pyotp.TOTP(secret)
    for _ in range(10):
        try:
            remaining = 30 - (int(time.time()) % 30)
            await asyncio.sleep(remaining)
            new_otp = totp.now()
            await safe_edit(
                message,
                f"{ce('success','✅')} <b>Your 2FA Code:</b> <code>{new_otp}</code>\n\n"
                f"{ce('waiting','⏳')} <i>(Live updating every 30 seconds...)</i>",
            )
        except Exception:
            break
    try:
        await safe_edit(
            message,
            f"{ce('success','✅')} <b>Last 2FA Code:</b> <code>{totp.now()}</code>\n\n"
            f"{ce('ban','🛑')} <i>Live update stopped after 5 minutes. Send key again to restart.</i>",
        )
    except Exception:
        pass

# ════════════════════════════════════════════════════
#              EXTRACT OTP (CSV)
# ════════════════════════════════════════════════════
@dp.message(F.text == "EXTRACT OTP")
async def extract_otp_handler(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_maintenance(message.from_user.id, message=message):
        return
    uid = message.from_user.id
    rows = cursor.execute(
        "SELECT phone_number, otp_code, service_name, timestamp FROM otp_success_logs WHERE user_id=? AND timestamp >= datetime('now', '-1 day') ORDER BY timestamp DESC",
        (uid,),
    ).fetchall()
    valid_rows = [(p, o, s, t) for p, o, s, t in rows if p and o]
    if not valid_rows:
        await safe_send(message, f"{ce('folder','📭')} No successful OTP history found in the last 24 hours.")
        return
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["Phone Number", "OTP", "Service", "Time"])
    for phone, otp, svc, ts in valid_rows:
        w.writerow([phone, otp, svc or "", ts])
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc = BufferedInputFile(buf.getvalue().encode("utf-8"), filename=f"otp_history_{ts_str}.csv")
    caption = (
        f"{ce('cat','🐱')}{ce('phone','📱')} <b>OTP Export — Last 24 Hours</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{ce('chart','📊')} <b>Total OTP:</b> {len(valid_rows)}\n"
        f"{ce('info','💡')} <b>Period:</b> Last 24 Hours\n\n"
        f"{ce('success','✅')} <b>CSV file ready!</b>"
    )
    await message.answer_document(document=doc, caption=caption, parse_mode="HTML")

# ════════════════════════════════════════════════════
#                 STATUS
# ════════════════════════════════════════════════════
@dp.message(F.text == "STATUS")
async def show_bot_stats(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_maintenance(message.from_user.id, message=message):
        return
    top_countries = cursor.execute("""
        SELECT country_code, COUNT(*) as cnt FROM (
            SELECT substr(phone_number,1,2) as country_code FROM otp_success_logs
        ) GROUP BY country_code ORDER BY cnt DESC LIMIT 5
    """).fetchall()
    total_otp = cursor.execute("SELECT COUNT(*) FROM otp_success_logs").fetchone()[0]
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_otp = cursor.execute("SELECT COUNT(*) FROM otp_success_logs WHERE timestamp LIKE ?", (f"{today}%",)).fetchone()[0]

    country_lines = ""
    for idx, (code, cnt) in enumerate(top_countries, 1):
        country_lines += f"  <code>{idx}.</code> 🌐 {code} ➜ <b>{cnt}</b> hits\n"
    if not country_lines:
        country_lines = "  No data yet.\n"

    text = (
        f"{ce('chart','📊')} <b>Network Statistics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{ce('users','👥')} <b>Total Users:</b> {total_users}\n"
        f"{ce('success','✅')} <b>Total OTPs:</b> {total_otp}\n"
        f"{ce('fire','🔥')} <b>Today's OTPs:</b> {today_otp}\n\n"
        f"{ce('trophy','🏆')} <b>Top Active Countries:</b>\n"
        f"{country_lines}\n"
        f"{ce('star','⭐')} <b>Active Services:</b>\n"
        f"  • Facebook  • WhatsApp\n"
        f"  • Instagram • Telegram\n"
        f"  • New FB\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('info','💡')} <i>Tap any code to copy instantly!</i>"
    )
    await safe_send(message, text)

# ════════════════════════════════════════════════════
#             ADMIN PANEL
# ════════════════════════════════════════════════════
@dp.message(F.text == "ADMIN PANEL")
@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return
    await safe_send(message, f"{ce('gear','⚙️')} <b>Admin Panel</b>", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await safe_edit(callback.message, f"{ce('gear','⚙️')} <b>Admin Panel</b>", reply_markup=admin_menu())

@dp.callback_query(F.data == "close_admin_panel")
async def close_admin_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if is_admin(callback.from_user.id):
        await callback.answer()
        try:
            await callback.message.delete()
        except Exception:
            pass

# ════════════════════════════════════════════════════
#         DATABASE BACKUP & RESTORE
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "db_backup")
async def db_backup_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await callback.answer("Creating backup...")
    try:
        path = create_db_backup()
        fname = os.path.basename(path)
        size_kb = os.path.getsize(path) // 1024
        with open(path, "rb") as f:
            doc = BufferedInputFile(f.read(), filename=fname)
        caption = (
            f"{ce('backup','💾')} <b>Database Backup Created</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 <b>File:</b> <code>{fname}</code>\n"
            f"📦 <b>Size:</b> {size_kb} KB\n"
            f"🕐 <b>Time:</b> {datetime.now().strftime('%d %b %Y %H:%M:%S')}\n\n"
            f"{ce('success','✅')} Backup saved successfully!"
        )
        await bot.send_document(callback.from_user.id, document=doc, caption=caption, parse_mode="HTML")
        await safe_edit(
            callback.message,
            f"{ce('success','✅')} <b>Backup created:</b> <code>{fname}</code> ({size_kb} KB)",
            reply_markup=admin_back_btn(),
        )
    except Exception as e:
        await safe_edit(
            callback.message,
            f"{ce('error','❌')} Backup failed: <code>{e}</code>",
            reply_markup=admin_back_btn(),
        )

@dp.callback_query(F.data == "db_restore_list")
async def db_restore_list(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    backups = list_backups()
    b = InlineKeyboardBuilder()
    if backups:
        for fname, fpath, size_kb, mtime in backups[:10]:
            label = f"📁 {fname[:30]} ({size_kb}KB)"
            b.row(InlineKeyboardButton(text=label, callback_data=f"db_restore_{fname}"))
    b.row(InlineKeyboardButton(text="📤 Upload .db File", callback_data="db_restore_upload", icon_custom_emoji_id=E["restore"]))
    b.row(InlineKeyboardButton(text="◀️ Back", callback_data="admin_back", icon_custom_emoji_id=E["back"]))

    count = len(backups)
    text = (
        f"{ce('restore','♻️')} <b>Database Restore</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 <b>Available Backups:</b> {count}\n\n"
        f"<i>Select a backup to restore, or upload a .db file.</i>\n\n"
        f"{ce('warning','⚠️')} <b>Warning:</b> Restoring will overwrite current data!"
    )
    await safe_edit(callback.message, text, reply_markup=b.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("db_restore_") & ~F.data.in_({"db_restore_list", "db_restore_upload"}))
async def db_restore_confirm(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    fname = callback.data[11:]
    fpath = os.path.join(BACKUP_DIR, fname)
    if not os.path.isfile(fpath):
        await callback.answer("Backup file not found!", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Yes, Restore", callback_data=f"db_do_restore_{fname}"),
        InlineKeyboardButton(text="❌ Cancel",        callback_data="db_restore_list"),
    )
    await safe_edit(
        callback.message,
        f"{ce('warning','⚠️')} <b>Confirm Restore?</b>\n\n"
        f"File: <code>{fname}</code>\n\n"
        f"This will <b>overwrite all current data</b>. Are you sure?",
        reply_markup=b.as_markup(),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("db_do_restore_"))
async def db_do_restore(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    fname = callback.data[14:]
    fpath = os.path.join(BACKUP_DIR, fname)
    await callback.answer("Restoring...")
    if restore_db_from_file(fpath):
        await safe_edit(
            callback.message,
            f"{ce('success','✅')} <b>Database restored successfully!</b>\n\n"
            f"From: <code>{fname}</code>\n\n"
            f"{ce('warning','⚠️')} Bot may need to be restarted.",
            reply_markup=admin_back_btn(),
        )
    else:
        await safe_edit(
            callback.message,
            f"{ce('error','❌')} Restore failed. The file may be corrupted.",
            reply_markup=admin_back_btn(),
        )

@dp.callback_query(F.data == "db_restore_upload")
async def db_restore_upload_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('restore','♻️')} Please send the <b>.db backup file</b> to restore:")
    await state.set_state(AdminStates.waiting_db_restore_file)
    await callback.answer()

@dp.message(AdminStates.waiting_db_restore_file, F.document)
async def db_restore_file_received(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    doc = message.document
    if not doc.file_name.endswith(".db"):
        await safe_send(message, f"{ce('error','❌')} Only <b>.db</b> files are accepted.")
        return
    wait_msg = await safe_send(message, f"{ce('waiting','⏳')} Processing backup file...")
    try:
        file = await bot.get_file(doc.file_id)
        downloaded = await bot.download_file(file.file_path)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(BACKUP_DIR, f"uploaded_{ts}.db")
        with open(temp_path, "wb") as f:
            f.write(downloaded.read())
        if restore_db_from_file(temp_path):
            await safe_edit(
                wait_msg,
                f"{ce('success','✅')} <b>Database restored from uploaded file!</b>\n\n"
                f"{ce('warning','⚠️')} Restart the bot for full effect.",
            )
        else:
            await safe_edit(wait_msg, f"{ce('error','❌')} Restore failed. File may be corrupted.")
    except Exception as e:
        await safe_edit(wait_msg, f"{ce('error','❌')} Error: <code>{e}</code>")
    await state.clear()

# ════════════════════════════════════════════════════
#              MAINTENANCE TOGGLE
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized!", show_alert=True)
        return
    new_val = "off" if is_maintenance_mode() else "on"
    cursor.execute("UPDATE config SET value=? WHERE key='maintenance_mode'", (new_val,))
    db.commit()
    await callback.answer(f"Maintenance mode turned {'ON' if new_val == 'on' else 'OFF'}", show_alert=True)
    await safe_edit(callback.message, f"{ce('gear','⚙️')} <b>Admin Panel</b>", reply_markup=admin_menu())

# ════════════════════════════════════════════════════
#              BAN / UNBAN
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "ban_user_btn")
async def ban_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('ban','🚫')} Enter the <b>User ID</b> to ban:")
    await state.set_state(AdminStates.waiting_ban_user)
    await callback.answer()

@dp.message(AdminStates.waiting_ban_user)
async def process_ban(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    uid = message.text.strip()
    if not uid.isdigit():
        await safe_send(message, f"{ce('error','❌')} Invalid ID. Must be numeric.")
        return
    cursor.execute("UPDATE users SET is_banned=1 WHERE id=?", (uid,))
    db.commit()
    await safe_send(message, f"{ce('success','✅')} User <code>{uid}</code> has been <b>banned</b>.")
    await state.clear()

@dp.callback_query(F.data == "unban_user_btn")
async def unban_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('success','✅')} Enter the <b>User ID</b> to unban:")
    await state.set_state(AdminStates.waiting_unban_user)
    await callback.answer()

@dp.message(AdminStates.waiting_unban_user)
async def process_unban(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    uid = message.text.strip()
    if not uid.isdigit():
        await safe_send(message, f"{ce('error','❌')} Invalid ID.")
        return
    cursor.execute("UPDATE users SET is_banned=0 WHERE id=?", (uid,))
    db.commit()
    await safe_send(message, f"{ce('success','✅')} User <code>{uid}</code> has been <b>unbanned</b>.")
    await state.clear()

# ════════════════════════════════════════════════════
#              ADD BALANCE (Admin)
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "add_balance")
async def add_balance_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(
        callback.message,
        f"{ce('money','💰')} Enter <b>User ID amount</b> (e.g. <code>123456789 100</code>):",
    )
    await state.set_state(AdminStates.waiting_add_balance)
    await callback.answer()

@dp.message(AdminStates.waiting_add_balance)
async def process_add_balance(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) != 2:
        await safe_send(message, f"{ce('error','❌')} Format: <code>user_id amount</code>")
        return
    uid_str, amt_str = parts
    if not uid_str.isdigit():
        await safe_send(message, f"{ce('error','❌')} Invalid user ID.")
        return
    try:
        amt = float(amt_str)
    except ValueError:
        await safe_send(message, f"{ce('error','❌')} Invalid amount.")
        return
    uid = int(uid_str)
    row = cursor.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        await safe_send(message, f"{ce('error','❌')} User not found.")
        return
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amt, uid))
    db.commit()
    new_bal = get_user_balance(uid)
    await safe_send(
        message,
        f"{ce('success','✅')} Added <code>{amt:.2f}</code>৳ to <code>{uid}</code>\n"
        f"New balance: <code>{new_bal:.2f}</code>৳",
    )
    await state.clear()

# ════════════════════════════════════════════════════
#              SEARCH USER
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "search_user")
async def search_user_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('search','🔍')} Enter User ID or @username:")
    await state.set_state(AdminStates.waiting_search_user)
    await callback.answer()

@dp.message(AdminStates.waiting_search_user)
async def process_search_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    query = message.text.strip().lstrip("@")
    if query.isdigit():
        row = cursor.execute("SELECT id, balance, username, fullname FROM users WHERE id=?", (int(query),)).fetchone()
        if row:
            await show_user_info(message, row)
        else:
            await safe_send(message, f"{ce('error','❌')} User not found.")
    else:
        rows = cursor.execute("SELECT id, balance, username, fullname FROM users WHERE username LIKE ?", (f"%{query}%",)).fetchall()
        if rows:
            text = f"{ce('search','🔍')} <b>Search Results:</b>\n\n"
            for r in rows:
                text += f"• <code>{r[0]}</code> @{r[2]} — {r[1]:.2f}৳\n"
            await safe_send(message, text)
        else:
            await safe_send(message, f"{ce('error','❌')} No users found.")
    await state.clear()

async def show_user_info(message: types.Message, row):
    uid, bal, uname, fullname = row
    total_otp = cursor.execute("SELECT COUNT(*) FROM otp_success_logs WHERE user_id=?", (uid,)).fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_otp = cursor.execute("SELECT COUNT(*) FROM otp_success_logs WHERE user_id=? AND timestamp LIKE ?", (uid, f"{today}%")).fetchone()[0]
    banned = "🔴 Yes" if is_banned(uid) else "🟢 No"
    join_row = cursor.execute("SELECT join_date FROM users WHERE id=?", (uid,)).fetchone()
    join_date = join_row[0][:10] if join_row and join_row[0] else "Unknown"
    text = (
        f"{ce('users','👤')} <b>User Info</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👤 <b>Name:</b> {fullname}\n"
        f"📛 <b>Username:</b> @{uname}\n"
        f"💰 <b>Balance:</b> <code>{bal:.2f}</code>৳\n"
        f"📅 <b>Joined:</b> {join_date}\n"
        f"📊 <b>Total OTPs:</b> {total_otp}\n"
        f"📆 <b>Today's OTPs:</b> {today_otp}\n"
        f"🚫 <b>Banned:</b> {banned}\n"
    )
    await safe_send(message, text)

# ════════════════════════════════════════════════════
#              ADMIN STATS
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    total_users   = cursor.execute("SELECT COUNT(id) FROM users").fetchone()[0]
    banned_users  = cursor.execute("SELECT COUNT(id) FROM users WHERE is_banned=1").fetchone()[0]
    total_otp     = cursor.execute("SELECT COUNT(*) FROM otp_success_logs").fetchone()[0]
    today         = datetime.now().strftime("%Y-%m-%d")
    today_otp     = cursor.execute("SELECT COUNT(*) FROM otp_success_logs WHERE timestamp LIKE ?", (f"{today}%",)).fetchone()[0]
    total_manual  = cursor.execute("SELECT COUNT(*) FROM manual_services").fetchone()[0]
    total_nums    = cursor.execute("SELECT COUNT(*) FROM manual_numbers").fetchone()[0]
    db_size_kb    = os.path.getsize(DB_PATH) // 1024 if os.path.isfile(DB_PATH) else 0
    backup_count  = len(list_backups())

    text = (
        f"{ce('chart','📊')} <b>System Live Stats</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{ce('users','👥')} <b>Total Users:</b> {total_users}\n"
        f"{ce('ban','🚫')} <b>Banned Users:</b> {banned_users}\n\n"
        f"{ce('success','✅')} <b>Total OTPs:</b> {total_otp}\n"
        f"{ce('fire','🔥')} <b>Today's OTPs:</b> {today_otp}\n\n"
        f"{ce('package','📦')} <b>Manual Services:</b> {total_manual}\n"
        f"{ce('phone','📞')} <b>Total Numbers:</b> {total_nums}\n\n"
        f"{ce('database','💽')} <b>DB Size:</b> {db_size_kb} KB\n"
        f"{ce('backup','💾')} <b>Backups:</b> {backup_count}\n"
        f"📅 <b>Date:</b> {datetime.now().strftime('%d %b %Y %H:%M')}\n"
    )
    await safe_edit(callback.message, text, reply_markup=admin_back_btn())
    await callback.answer()

# ════════════════════════════════════════════════════
#              SET OTP CHANNEL
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "set_otp_channel")
async def set_otp_channel_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('signal','📡')} Enter the <b>Channel ID</b> for live OTP feed:")
    await state.set_state(AdminStates.waiting_otp_channel)
    await callback.answer()

@dp.message(AdminStates.waiting_otp_channel)
async def save_otp_channel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cid = message.text.strip()
    if not (cid.startswith("-100") and cid[1:].isdigit()):
        await safe_send(message, f"{ce('error','❌')} Provide a valid channel ID (-100... format).")
        return
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('otp_channel_id', ?)", (cid,))
    db.commit()
    await safe_send(message, f"{ce('success','✅')} OTP channel set: <code>{cid}</code>")
    await state.clear()

# ════════════════════════════════════════════════════
#              MANAGE ADMINS
# ════════════════════════════════════════════════════
def admin_management_menu() -> types.InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="➕ Add Admin",    callback_data="add_admin_btn",    icon_custom_emoji_id=E["add"]))
    b.row(InlineKeyboardButton(text="➖ Remove Admin", callback_data="remove_admin_btn", icon_custom_emoji_id=E["error"]))
    b.row(InlineKeyboardButton(text="📋 List Admins",  callback_data="list_admins",       icon_custom_emoji_id=E["folder"]))
    b.row(InlineKeyboardButton(text="◀️ Back",         callback_data="admin_back",        icon_custom_emoji_id=E["back"]))
    return b.as_markup()

@dp.callback_query(F.data == "manage_admins")
async def manage_admins_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('users','👥')} <b>Admin Management</b>:", reply_markup=admin_management_menu())
    await callback.answer()

@dp.callback_query(F.data == "add_admin_btn")
async def add_admin_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('add','➕')} Enter User ID to add as Admin:")
    await state.set_state(AdminStates.waiting_add_admin)
    await callback.answer()

@dp.message(AdminStates.waiting_add_admin)
async def add_admin(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    uid = message.text.strip()
    if not uid.isdigit():
        await safe_send(message, f"{ce('error','❌')} Invalid ID.")
        return
    cursor.execute("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
    db.commit()
    await safe_send(message, f"{ce('success','✅')} User <code>{uid}</code> is now an admin.")
    await state.clear()

@dp.callback_query(F.data == "remove_admin_btn")
async def remove_admin_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('error','❌')} Enter User ID to remove from Admins:")
    await state.set_state(AdminStates.waiting_remove_admin)
    await callback.answer()

@dp.message(AdminStates.waiting_remove_admin)
async def remove_admin(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    uid = message.text.strip()
    if uid == str(message.from_user.id):
        await safe_send(message, f"{ce('error','❌')} You cannot remove yourself.")
        return
    cursor.execute("DELETE FROM admins WHERE user_id=?", (uid,))
    db.commit()
    await safe_send(message, f"{ce('success','✅')} User <code>{uid}</code> is no longer an admin.")
    await state.clear()

@dp.callback_query(F.data == "list_admins")
async def list_admins(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    rows = cursor.execute("SELECT user_id FROM admins").fetchall()
    items = "".join(f"• <code>{uid}</code>\n" for (uid,) in rows) if rows else "No admins found."
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Back", callback_data="manage_admins", icon_custom_emoji_id=E["back"]))
    await safe_edit(callback.message, f"{ce('users','👥')} <b>Active Admins:</b>\n\n{items}", reply_markup=b.as_markup())
    await callback.answer()

# ════════════════════════════════════════════════════
#              BROADCAST
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_bc")
async def bc_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('broadcast','📣')} Send the broadcast message (text, photo, video, etc.):")
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_broadcast)
async def bc_send(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    users = cursor.execute("SELECT id FROM users").fetchall()
    await safe_send(message, f"{ce('waiting','⏳')} Sending broadcast to {len(users)} users...")
    success = 0
    for (uid,) in users:
        try:
            await bot.copy_message(chat_id=int(uid), from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await safe_send(message, f"{ce('success','✅')} Broadcast sent to <b>{success}/{len(users)}</b> users.")
    await state.clear()

# ════════════════════════════════════════════════════
#              TOP 10 USERS
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "top_10_users")
async def show_top_10_users(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    cursor.execute("DELETE FROM otp_success_logs WHERE timestamp < ?", (thirty_days_ago,))
    db.commit()
    rows = cursor.execute("""
        SELECT u.fullname, u.username, COUNT(o.id) as otp_count
        FROM otp_success_logs o
        JOIN users u ON o.user_id = u.id
        WHERE o.timestamp >= ?
        GROUP BY o.user_id
        ORDER BY otp_count DESC LIMIT 10
    """, (thirty_days_ago,)).fetchall()

    medals = ["🥇", "🥈", "🥉"]
    text = f"{ce('trophy','🏆')} <b>Top 10 Users (Last 30 Days)</b>\n\n"
    if rows:
        for idx, (fullname, username, count) in enumerate(rows):
            rank = medals[idx] if idx < 3 else f"<code>{idx+1}.</code>"
            uname_str = f"(@{username})" if username else ""
            text += f"{rank} {fullname or 'Unknown'} {uname_str} — <code>{count} OTP</code>\n"
    else:
        text += "No OTP history found."

    await safe_edit(callback.message, text, reply_markup=admin_back_btn())
    await callback.answer()

@dp.callback_query(F.data == "total_users")
async def show_total_users(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    count = cursor.execute("SELECT COUNT(id) FROM users").fetchone()[0]
    await safe_edit(callback.message, f"{ce('users','👥')} <b>Total Registered Users:</b> <code>{count}</code>", reply_markup=admin_back_btn())
    await callback.answer()

# ════════════════════════════════════════════════════
#              ADD MANUAL NUMBERS (with price)
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "add_manual_numbers")
async def add_manual_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback.message, f"{ce('folder','📂')} Send a <b>.txt file</b> with one phone number per line:")
    await state.set_state(AdminStates.waiting_manual_file)
    await callback.answer()

@dp.message(AdminStates.waiting_manual_file, F.document)
async def manual_file_received(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    doc = message.document
    if not doc.file_name.endswith(".txt"):
        await safe_send(message, f"{ce('error','❌')} Only <b>.txt</b> files accepted.")
        return
    try:
        file = await bot.get_file(doc.file_id)
        dl = await bot.download_file(file.file_path)
        content = dl.read().decode("utf-8", errors="ignore")
    except Exception as e:
        await safe_send(message, f"{ce('error','❌')} File read error: <code>{e}</code>")
        await state.clear()
        return
    numbers = [ln.strip() for ln in content.strip().split("\n") if ln.strip()]
    if not numbers:
        await safe_send(message, f"{ce('error','❌')} No valid numbers found in file.")
        await state.clear()
        return
    await state.update_data(manual_numbers=numbers)
    await safe_send(
        message,
        f"{ce('add','➕')} Enter <b>service name</b>\n"
        f"Options: <code>WHATSAPP</code> / <code>FACEBOOK</code> / <code>INSTAGRAM</code> / <code>TELEGRAM</code> / <code>NEW FB</code>",
    )
    await state.set_state(AdminStates.waiting_manual_svc_name)

@dp.message(AdminStates.waiting_manual_svc_name)
async def manual_svc_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(manual_svc=message.text.strip().upper())
    await safe_send(message, f"{ce('globe','🌍')} Enter <b>country name</b> (e.g. Bangladesh):")
    await state.set_state(AdminStates.waiting_manual_country)

@dp.message(AdminStates.waiting_manual_country)
async def manual_country(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(manual_country=message.text.strip())
    await safe_send(message, f"{ce('add','➕')} How many numbers per click? (e.g. 3):")
    await state.set_state(AdminStates.waiting_manual_give)

@dp.message(AdminStates.waiting_manual_give)
async def manual_give_amount(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        give = int(message.text)
        if give < 1:
            raise ValueError
    except ValueError:
        await safe_send(message, f"{ce('error','❌')} Enter a positive number.")
        return
    await state.update_data(manual_give=give)
    await safe_send(
        message,
        f"{ce('money','💰')} Enter <b>price per number</b> in ৳ (use <code>0</code> for FREE):",
    )
    await state.set_state(AdminStates.waiting_manual_price)

@dp.message(AdminStates.waiting_manual_price)
async def manual_price_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text)
        if price < 0:
            raise ValueError
    except ValueError:
        await safe_send(message, f"{ce('error','❌')} Enter a valid non-negative number.")
        return
    await state.update_data(manual_price=price)
    await safe_send(message, f"{ce('waiting','⏳')} Enter <b>cooldown</b> in seconds (e.g. 60):")
    await state.set_state(AdminStates.waiting_manual_cooldown)

@dp.message(AdminStates.waiting_manual_cooldown)
async def manual_cooldown_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        cooldown = int(message.text)
        if cooldown < 0:
            raise ValueError
    except ValueError:
        await safe_send(message, f"{ce('error','❌')} Enter a valid number.")
        return
    data = await state.get_data()
    svc = data["manual_svc"]
    country = data["manual_country"]
    give = data["manual_give"]
    price = data["manual_price"]
    numbers = data["manual_numbers"]
    flag = get_flag_emoji(country[:2].upper()) if country else ""
    cursor.execute(
        "INSERT INTO manual_services (service_name, country_name, flag, give_amount, price, stock, cooldown) VALUES (?,?,?,?,?,?,?)",
        (svc, country, flag, give, price, len(numbers), cooldown),
    )
    svc_id = cursor.lastrowid
    for num in numbers:
        cursor.execute("INSERT INTO manual_numbers (service_id, number) VALUES (?,?)", (svc_id, num))
    db.commit()
    b = InlineKeyboardBuilder()
    b.button(text="📣 Broadcast",  callback_data=f"m_bc_{svc_id}", icon_custom_emoji_id=E["broadcast"])
    b.button(text="✖️ Close",      callback_data="close_admin_panel", icon_custom_emoji_id=E["error"])
    price_str = "🆓 Free" if price <= 0 else f"💰 {price:.2f}৳"
    await safe_send(
        message,
        f"{ce('success','✅')} Added <b>{len(numbers)}</b> numbers to <b>{svc} — {country}</b>\n"
        f"Price: {price_str}  ·  Cooldown: <code>{cooldown}s</code>\n\nBroadcast this to all users?",
        reply_markup=b.as_markup(),
    )
    await state.clear()

@dp.callback_query(F.data.startswith("m_bc_"))
async def broadcast_manual_addition(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    svc_id = int(callback.data.split("_")[2])
    row = cursor.execute("SELECT service_name, country_name, flag, stock, price FROM manual_services WHERE id=?", (svc_id,)).fetchone()
    if not row:
        await callback.answer("Service not found.", show_alert=True)
        return
    svc, country, flag, stock, price = row
    price_str = "🆓 Free" if price <= 0 else f"💰 {price:.2f}৳"
    bc_text = (
        f"{ce('fire','🔥')} <b>New Numbers Added!</b> {ce('fire','🔥')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('folder','📂')} <b>Service:</b> {svc}\n"
        f"{ce('globe','🌍')} <b>Country:</b> {flag} {country}\n"
        f"{ce('chart','📊')} <b>Stock:</b> {stock} numbers\n"
        f"{ce('money','💰')} <b>Price:</b> {price_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ce('next','🚀')} Go to <b>GET NUMBER</b> and grab yours now!"
    )
    await safe_edit(callback.message, f"{ce('waiting','⏳')} Sending broadcast...")
    users = cursor.execute("SELECT id FROM users").fetchall()
    success = 0
    for (uid,) in users:
        try:
            await bot.send_message(int(uid), bc_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await safe_edit(callback.message, f"{ce('success','✅')} Broadcast sent to <b>{success}</b> users.")

# ════════════════════════════════════════════════════
#           MANAGE MANUAL NUMBERS + Edit Price
# ════════════════════════════════════════════════════
@dp.callback_query(F.data == "manage_manual_numbers")
async def manage_manual_numbers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    services = cursor.execute("SELECT id, service_name, country_name, stock, price FROM manual_services").fetchall()
    if not services:
        await callback.answer("No manual services.", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for svc_id, svc, country, stock, price in services:
        price_str = "🆓" if price <= 0 else f"{price:.2f}৳"
        b.row(
            InlineKeyboardButton(
                text=f"💰 {svc} — {country} ({stock} left · {price_str})",
                callback_data=f"edit_price_{svc_id}",
                icon_custom_emoji_id=E["money"],
            ),
        )
        b.row(
            InlineKeyboardButton(
                text=f"🗑 Delete {svc} — {country}",
                callback_data=f"del_manual_{svc_id}",
                icon_custom_emoji_id=E["delete"],
            ),
        )
    b.row(InlineKeyboardButton(text="◀️ Back", callback_data="admin_back", icon_custom_emoji_id=E["back"]))
    await safe_edit(
        callback.message,
        f"{ce('folder','📋')} <b>Manual Services</b>\n"
        f"<i>Tap 💰 to edit price · 🗑 to delete</i>",
        reply_markup=b.as_markup(),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_price_"))
async def edit_price_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    svc_id = int(callback.data[11:])
    row = cursor.execute("SELECT service_name, country_name, price FROM manual_services WHERE id=?", (svc_id,)).fetchone()
    if not row:
        await callback.answer("Service not found.", show_alert=True)
        return
    svc, country, price = row
    current = "🆓 Free" if price <= 0 else f"{price:.2f}৳"
    await safe_edit(
        callback.message,
        f"{ce('money','💰')} <b>Edit Price</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Service: <b>{svc} — {country}</b>\n"
        f"Current: {current}\n\n"
        f"Enter new price in ৳ (use <code>0</code> for FREE):",
    )
    await state.update_data(edit_svc_id=svc_id)
    await state.set_state(AdminStates.waiting_edit_price)
    await callback.answer()

@dp.message(AdminStates.waiting_edit_price)
async def edit_price_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text)
        if price < 0:
            raise ValueError
    except ValueError:
        await safe_send(message, f"{ce('error','❌')} Enter a valid non-negative number.")
        return
    data = await state.get_data()
    svc_id = data.get("edit_svc_id")
    if not svc_id:
        await safe_send(message, f"{ce('error','❌')} Session expired.")
        await state.clear()
        return
    cursor.execute("UPDATE manual_services SET price=? WHERE id=?", (price, svc_id))
    db.commit()
    price_str = "🆓 Free" if price <= 0 else f"💰 {price:.2f}৳"
    await safe_send(message, f"{ce('success','✅')} Price updated to {price_str}")
    await state.clear()

@dp.callback_query(F.data.startswith("del_manual_"))
async def delete_manual_service(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id):
        return
    svc_id = int(callback.data[11:])
    cursor.execute("DELETE FROM manual_numbers WHERE service_id=?", (svc_id,))
    cursor.execute("DELETE FROM manual_services WHERE id=?", (svc_id,))
    db.commit()
    await callback.answer("Deleted.", show_alert=True)
    await manage_manual_numbers(callback, state)

# ════════════════════════════════════════════════════
#              LIFECYCLE
# ════════════════════════════════════════════════════
async def on_shutdown():
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()

async def on_startup():
    asyncio.create_task(process_manual_expiry())
    logger.info("✅ Bot started successfully!")

dp.shutdown.register(on_shutdown)
dp.startup.register(on_startup)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

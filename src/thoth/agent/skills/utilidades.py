"""Skills de utilidade: horas, data, clima, cotação, cálculo, lembrete, pesquisa, música."""
from __future__ import annotations

import ast
import datetime
import json
import logging
import math
import operator
import threading
import urllib.parse
import urllib.request

from thoth.core.config import get_settings
from thoth.agent.skills.registry import get_speaker, tool

log = logging.getLogger("thoth.skills.utilidades")

_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _http_json(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "thoth-marco/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fixa/confiável)
        return json.loads(r.read().decode("utf-8"))


# --- hora e data ----------------------------------------------------------
@tool("que_horas", "Diz a hora atual. Use quando perguntarem as horas.")
def que_horas(_args: dict) -> str:
    return f"Agora são {datetime.datetime.now().strftime('%H:%M')}."


@tool("que_dia", "Diz a data de hoje e o dia da semana. Use para 'que dia é hoje', 'que data é hoje'.")
def que_dia(_args: dict) -> str:
    d = datetime.date.today()
    return f"Hoje é {_DIAS[d.weekday()]}, {d.day} de {_MESES[d.month - 1]} de {d.year}."


# --- clima ----------------------------------------------------------------
_WMO = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "com névoa", 48: "com névoa e geada", 51: "com garoa fraca", 53: "com garoa",
    55: "com garoa forte", 56: "com garoa congelante", 57: "com garoa congelante forte",
    61: "com chuva fraca", 63: "com chuva", 65: "com chuva forte",
    66: "com chuva congelante", 67: "com chuva congelante forte",
    71: "com neve fraca", 73: "com neve", 75: "com neve forte", 77: "com flocos de neve",
    80: "com pancadas de chuva fracas", 81: "com pancadas de chuva", 82: "com pancadas fortes de chuva",
    85: "com pancadas de neve", 86: "com pancadas fortes de neve",
    95: "com tempestade", 96: "com tempestade e granizo", 99: "com tempestade forte e granizo",
}


@tool(
    "consultar_clima",
    "Consulta o clima/tempo atual de uma cidade. Use para 'como está o tempo', 'vai chover', "
    "'qual a temperatura'. Se a cidade não for dita, usa a cidade padrão.",
    {"type": "object",
     "properties": {"cidade": {"type": "string", "description": "nome da cidade (opcional)"}}},
)
def consultar_clima(args: dict) -> str:
    s = get_settings()
    cidade = (args.get("cidade") or "").strip() or s.default_city
    try:
        geo = _http_json("https://geocoding-api.open-meteo.com/v1/search?" +
                         urllib.parse.urlencode({"name": cidade, "count": 1,
                                                 "language": "pt", "format": "json"}))
        res = geo.get("results") or []
        if not res:
            return f"Não encontrei a cidade {cidade}."
        loc = res[0]
        nome = loc.get("name", cidade)
        w = _http_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,weather_code", "timezone": "auto",
        }))
        cur = w["current"]
        desc = _WMO.get(cur.get("weather_code"), "tempo indefinido")
        temp = round(cur["temperature_2m"])
        hum = cur.get("relative_humidity_2m")
        return f"Em {nome}, agora está {temp} graus, {desc}, com umidade de {hum} por cento."
    except Exception as exc:  # noqa: BLE001
        return f"Não consegui consultar o clima ({type(exc).__name__})."


# --- cotação --------------------------------------------------------------
_MOEDAS = {"dolar": "USD", "dólar": "USD", "dolares": "USD", "dólares": "USD",
           "euro": "EUR", "euros": "EUR", "libra": "GBP", "libras": "GBP",
           "bitcoin": "BTC", "btc": "BTC"}
_NOMES = {"USD": "dólar", "EUR": "euro", "GBP": "libra", "BTC": "bitcoin"}


def _brl(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


@tool(
    "consultar_cotacao",
    "Consulta a cotação de moedas em reais (dólar, euro, libra, bitcoin). Use para "
    "'quanto está o dólar', 'cotação do bitcoin'. Sem moeda, retorna dólar e bitcoin.",
    {"type": "object",
     "properties": {"moeda": {"type": "string",
                              "description": "dólar, euro, libra ou bitcoin (opcional)"}}},
)
def consultar_cotacao(args: dict) -> str:
    pedido = (args.get("moeda") or "").strip().lower()
    codes = [_MOEDAS[pedido]] if pedido in _MOEDAS else ["USD", "BTC"]
    try:
        pares = ",".join(f"{c}-BRL" for c in codes)
        data = _http_json("https://economia.awesomeapi.com.br/last/" + pares)
        falas = []
        for c in codes:
            k = f"{c}BRL"
            if k in data:
                falas.append(f"o {_NOMES.get(c, c)} está em {_brl(float(data[k]['bid']))}")
        if not falas:
            return "Não consegui obter a cotação agora."
        frase = ", ".join(falas) + "."
        return frase[0].upper() + frase[1:]
    except Exception as exc:  # noqa: BLE001
        return f"Não consegui consultar a cotação ({type(exc).__name__})."


# --- calculadora (avaliação segura por AST) -------------------------------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos}
_NAMES = {"pi": math.pi, "e": math.e}
_FUNCS = {"sqrt": math.sqrt, "raiz": math.sqrt, "sin": math.sin, "cos": math.cos,
          "tan": math.tan, "log": math.log, "log10": math.log10, "abs": abs, "round": round}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if type(node.op) is ast.Pow and (abs(right) > 1000 or (abs(left) > 1 and abs(right) > 100)):
            raise ValueError("expoente grande demais")  # evita travar a CPU
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS):
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("expressão não suportada")


@tool(
    "calcular",
    "Resolve uma conta ou expressão matemática. Passe a expressão com dígitos e operadores "
    "(+, -, *, /, **). Para porcentagem converta (ex.: 15% de 200 = 200*15/100).",
    {"type": "object",
     "properties": {"expressao": {"type": "string", "description": "ex.: 200*15/100, 3*47, sqrt(2)"}},
     "required": ["expressao"]},
)
def calcular(args: dict) -> str:
    expr = (args.get("expressao") or "").strip()
    if not expr:
        return "Diga a conta que devo calcular."
    norm = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    try:
        val = _eval(ast.parse(norm, mode="eval").body)
        if isinstance(val, float):
            val = int(val) if val.is_integer() else round(val, 4)
        return f"O resultado é {val}."
    except Exception:  # noqa: BLE001
        return f"Não consegui calcular '{expr}'."


# --- lembrete / timer -----------------------------------------------------
@tool(
    "criar_lembrete",
    "Cria um lembrete/timer que avisa por voz depois de um tempo. Use para 'me avise em "
    "10 minutos', 'marca 5 minutos', 'me lembra de X em Y minutos'.",
    {"type": "object",
     "properties": {
         "minutos": {"type": "number", "description": "minutos até avisar"},
         "segundos": {"type": "number", "description": "segundos até avisar"},
         "mensagem": {"type": "string", "description": "o que lembrar (opcional)"}},
     },
)
def criar_lembrete(args: dict) -> str:
    try:
        total = float(args.get("minutos") or 0) * 60 + float(args.get("segundos") or 0)
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0:
        return "Diga em quantos minutos ou segundos devo te avisar."
    if total > 24 * 3600:  # teto de 24h: evita timers absurdos / threads penduradas
        return "Esse tempo é longo demais. Posso te avisar em até 24 horas."
    msg = (args.get("mensagem") or "").strip() or "seu tempo acabou"
    speaker = get_speaker()

    def _fire() -> None:
        texto = f"Lembrete: {msg}."
        try:
            (speaker or log.info)(texto)
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao falar o lembrete: %s", exc)

    timer = threading.Timer(total, _fire)
    timer.daemon = True
    timer.start()
    if total >= 60:
        m, sec = int(total // 60), int(total % 60)
        quando = f"{m} minuto{'s' if m != 1 else ''}" + (
            f" e {sec} segundo{'s' if sec != 1 else ''}" if sec else "")
    else:
        sec = int(total)
        quando = f"{sec} segundo{'s' if sec != 1 else ''}"
    return f"Combinado, vou te avisar em {quando}."


# --- pesquisa e música (mantidas da versão anterior) ----------------------
@tool(
    "pesquisar_wikipedia",
    "Busca um resumo curto sobre um tema, pessoa ou lugar na Wikipédia.",
    {"type": "object",
     "properties": {"tema": {"type": "string", "description": "o que pesquisar"}},
     "required": ["tema"]},
)
def pesquisar_wikipedia(args: dict) -> str:
    tema = (args.get("tema") or "").strip()
    if not tema:
        return "Tema vazio."
    try:
        import wikipedia

        wikipedia.set_lang("pt")
        return wikipedia.summary(tema, sentences=2)
    except ImportError:
        return "Biblioteca wikipedia não instalada."
    except Exception as exc:  # noqa: BLE001
        return f"Não achei um resumo confiável sobre '{tema}' ({type(exc).__name__})."


@tool(
    "tocar_musica",
    "Toca uma música ou vídeo no YouTube (abre no navegador).",
    {"type": "object",
     "properties": {"busca": {"type": "string", "description": "nome da música/artista"}},
     "required": ["busca"]},
)
def tocar_musica(args: dict) -> str:
    busca = (args.get("busca") or "").strip()
    if not busca:
        return "Nome da música vazio."
    try:
        import pywhatkit

        pywhatkit.playonyt(busca)
        return f"Tocando {busca} no YouTube."
    except ImportError:
        return "Para tocar música, instale: pip install pywhatkit."
    except Exception as exc:  # noqa: BLE001
        return f"Não consegui tocar '{busca}' ({type(exc).__name__})."

#!/usr/bin/env python3
"""
ELARA Content Creator — Streamlit Cloud Version
Login + Gutschein-System
Mode A: Reel Hook Generator
Mode B: Story Creator (Julia Trost Storytelling)
"""

import streamlit as st
import anthropic
import os
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="ELARA Content Creator",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── FARBEN ─────────────────────────────────────────────────────────────────────
LILA      = "#6C63FF"
PINK      = "#E84393"
SOFT_LILA = "#F0EEFF"
SOFT_PINK = "#fff5fb"
DARK      = "#1A1A1A"
GREY      = "#888888"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap');

* {{ font-family: 'DM Sans', sans-serif !important; }}
h1, h2, h3 {{ font-family: 'Playfair Display', serif !important; }}

.block-container {{ max-width: 800px; padding-top: 1.5rem; padding-bottom: 4rem; }}

.app-title {{
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    font-weight: 700;
    color: {LILA};
    text-align: center;
    margin: 0.5rem 0 0.2rem;
}}
.app-sub {{
    font-size: 0.95rem;
    color: {GREY};
    text-align: center;
    margin-bottom: 1.5rem;
}}
.step-badge {{
    background: {LILA};
    color: white;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 8px;
}}
.story-frame {{
    background: {SOFT_PINK};
    border-left: 4px solid {PINK};
    border-radius: 4px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.6rem;
    font-size: 0.95rem;
}}
.login-box {{
    background: {SOFT_LILA};
    border-left: 4px solid {LILA};
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    margin: 0.8rem 0;
    color: {DARK};
    font-size: 0.95rem;
    line-height: 1.8;
}}
.hint {{
    color: #999;
    font-size: 0.83rem;
    font-style: italic;
    text-align: center;
    margin: 0.4rem 0 0.8rem;
}}
.footer-copy {{
    text-align: center;
    color: #ccc;
    font-size: 0.7rem;
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #eee;
}}
div.stButton > button {{
    background: {LILA};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.65rem 1.8rem;
    font-weight: 600;
    font-size: 0.95rem;
    width: 100%;
    transition: opacity 0.2s;
}}
div.stButton > button:hover {{ opacity: 0.85; background: {LILA} !important; color: white !important; }}
</style>
""", unsafe_allow_html=True)


# ── DATEIPFADE & KONSTANTEN ────────────────────────────────────────────────────
CODES_FILE  = Path(__file__).parent / "content-creator-codes.json"
HEADER_IMG  = Path(__file__).parent / "assets" / "header.jpg"
SHEET_ID    = "1uLW2zatmbeYXrdRix99P-EliLN8Ffam3FscqJsC09v4"
SHEET_TAB   = "ContentCreator-Codes"


# ── GOOGLE SHEETS HELPER ───────────────────────────────────────────────────────
def _fix_pem_key(key: str) -> str:
    key = key.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n").strip()
    begin = "-----BEGIN PRIVATE KEY-----"
    end   = "-----END PRIVATE KEY-----"
    inner = key
    for marker in [begin, end, "-----BEGIN RSA PRIVATE KEY-----", "-----END RSA PRIVATE KEY-----"]:
        inner = inner.replace(marker, "")
    inner = "".join(inner.split())
    chunks = [inner[i:i+64] for i in range(0, len(inner), 64)]
    return begin + "\n" + "\n".join(chunks) + "\n" + end + "\n"


def _get_gsheet_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = _fix_pem_key(creds_dict["private_key"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


# ── CODE-PRÜFUNG (Google Sheet) ────────────────────────────────────────────────
def check_code(code: str) -> tuple:
    """Prüft Code gegen Google Sheet. Fallback auf JSON falls Sheet nicht erreichbar."""
    code = code.upper().strip()
    if not code:
        return False, ""

    # Primär: Google Sheet
    try:
        gc     = _get_gsheet_client()
        wb     = gc.open_by_key(SHEET_ID)
        sheet  = wb.worksheet(SHEET_TAB)
        rows   = sheet.get_all_records()
        for row in rows:
            row_code = str(row.get("Code", "")).upper().strip()
            if row_code == code:
                aktiv = str(row.get("Aktiv", "")).upper().strip()
                if aktiv in ("TRUE", "JA", "1", "WAHR"):
                    return True, "Code akzeptiert."
                else:
                    return False, "Dieser Code ist nicht mehr aktiv."
        return False, "Dieser Code ist nicht gültig."
    except Exception:
        pass

    # Fallback: JSON (für lokale Entwicklung)
    if CODES_FILE.exists():
        codes  = json.loads(CODES_FILE.read_text(encoding="utf-8"))
        lookup = code
        if code not in codes:
            parts = code.split("-")
            if len(parts) >= 2:
                prefix = parts[0] + "-*"
                if prefix in codes:
                    lookup = prefix
        if lookup in codes:
            v = codes[lookup]
            if not v.get("active", True):
                return False, "Dieser Code ist nicht mehr aktiv."
            return True, "Code akzeptiert."

    return False, "Dieser Code ist nicht gültig."


def check_email_access(email: str) -> bool:
    email = email.strip().lower()
    if not email:
        return False
    try:
        raw = st.secrets.get("AUTHORIZED_EMAILS", "")
        if raw:
            authorized = [e.strip().lower() for e in raw.split(",") if e.strip()]
            if email in authorized:
                return True
    except Exception:
        pass
    return False


# ── API CLIENT ─────────────────────────────────────────────────────────────────
def get_client():
    key = ""
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    if not key:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=key) if key else None


# ── SYSTEM PROMPTS ─────────────────────────────────────────────────────────────
SYSTEM_REEL = """Du bist ein Experte für virale Instagram Reel Hooks und Captions.

Du kennst diese 13 psychologisch wirksamen Hook-Typen:

— GRUPPE A: KLASSISCHE LÜCKEN-HOOKS —
1. INSIDER-VERRAT: "[Experte] verriet etwas, das kaum jemand kennt (und fast alle machen diesen Fehler)"
2. SCHOCK-ERGEBNIS: "[Person/Studie] zeigte X – das Ergebnis traf alle unvorbereitet (betrifft fast jeden)"
3. STILLE-KATASTROPHE: "[Normales Verhalten] – [Zeit] später [unbemerkte Konsequenz] (passiert täglich)"
4. WARUM-GEHEIMNIS: "Warum [Alltägliches] [verborgener Grund] (hat nichts mit [Offensichtlichem] zu tun)"
5. KONTRA-INTUITION: "Die meisten glauben X – die Wahrheit ist das Gegenteil (dieser Irrtum kostet [Preis])"
6. EXPERTEN-ZITAT: "Ein [Harvard/CIA/Militär]-Experte sagte einen Satz, der [extreme Wirkung] (sofort klar warum)"
7. WENN-DANN-WARNUNG: "[Normales Verhalten] – dann [unerwartete Folge] (die meisten bemerken es nie)"
8. ZAHLEN-SCHOCK: "[Spezifische Zahl/Zeit] – [überraschendes Ergebnis] (kaum jemand spricht darüber)"

— GRUPPE B: WIDERSPRUCH & LÜCKEN-HOOKS (Ich-Stimme / konkretes Versprechen) —
9. DAS-KLINGT-FALSCH: Widerspruch in Zeile 1 — Gehirn muss weiterlesen. Endet mit konkretem Ergebnis-Hint.
   Formel: "Ich habe [kontraintuitives Verhalten] — und [überraschendes Ergebnis]. Das klingt falsch. Ist es aber nicht."
10. DREI-DINGE: Konkrete Zahl + reale Bedrohung + spezifischer Verlust. Kein vager Schmerz — echte Zahl.
   Formel: "Diese [Zahl] [konkretes Ding] kosten [Zielgruppe] jedes Jahr [konkrete Zahl/Betrag] — und sie [tun es täglich]."
11. ICH-DACHTE: Ich-Perspektive + konkretes Versprechen was die Person nach dem Weiterlesen bekommt.
   Formel: "Jahrelang dachte ich, [falsche Annahme]. Dann fand ich heraus, welche [Zahl] [konkretes Was] — und wie ich sie in [Zeitraum] aufgelöst hab."
12. NICHT-GLAUBEN: Drei "ohne"-Aussagen + abschliessender Ich-Beweis.
   Formel: "[konkretes Ergebnis] — ohne [Erwartetes 1], ohne [Erwartetes 2], ohne [Erwartetes 3]. Ich zeig dir die [Zahl] Schritte."
13. DU-MACHST-ES-FALSCH: Direkte Ansprache + konkreter stuck-point mit Zahl statt vager Emotion.
   Formel: "Wenn du [Situation] — machst du [Ding] das sich wie [positives Gefühl] anfühlt, aber dich bei [konkrete Zahl/Situation] festhält."

---

DAS GESETZ DES STARKEN HOOKS:
Jeder Hook braucht ZWEI Elemente — nicht nur eines:
1. DIE LÜCKE: Problem, Schmerz, Widerspruch — die Person erkennt sich
2. DER ERGEBNIS-HINT: Ein konkreter Hinweis WAS sie bekommt — nie die volle Lösung, aber immer eine Richtung

VERBOTEN:
- Vage Enden: "was wirklich dazwischensteht" / "was sie sich wünschen" / "genau dort festhält"
- Fragen am Ende: "Klingt unmöglich?" — Fragen bremsen, Versprechen ziehen
- Abstrakte Verluste: "tausende Euro" → immer konkret: "bis zu 30.000€ im Jahr"

PFLICHT-FORMEL für den Abschluss jedes Hooks — eine davon:
A) "...ich zeig dir die [Zahl] [Was] — danach [konkretes Ergebnis]."
B) "...welche [Zahl] [Was] das sind — und wie ich sie in [Zeitraum] aufgelöst hab."
C) "[konkreter stuck-point mit Zahl] obwohl sie [tägliche Handlung]."

REGELN:
- Umlaute normal: ä, ö, ü, Ä, Ö, Ü
- ss statt ß (kein ß)
- Kurze Sätze. Kein Schachtelbau.
- Zeigen nicht behaupten
- Kein 'Link in Bio', kein direkter Verkauf
- Sprache: Deutsch"""

SYSTEM_STORY = """Du bist ein Experte für Instagram Story-Texte nach der Julia Trost Storytelling-Strategie.

Die Struktur ist immer:
1. SITUATION — die Alltagsszene, genau so wie sie passiert ist. Nah, konkret, wiedererkennbar.
2. LEARNING — die Erkenntnis, die in dieser Situation steckt. Überraschend, tief, nicht offensichtlich.
3. BRIDGE — die Überleitung: Was hat das mit der Zielgruppe zu tun? Warum ist es für sie relevant?
4. CTA — Code-Wort mit klarem Nutzenversprechen.

Prinzipien:
- Die Situation muss sich anfühlen wie ein Film-Ausschnitt. Kein Erklärmodus.
- Das Learning kommt aus der Situation heraus — es wird nicht aufgesetzt.
- Die Bridge verbindet persönlich mit universal, ohne zu predigen.
- Kurze Sätze. Pausen. Jeder Satz steht für sich.
- Keine Erklärungen. Keine Moral. Nur das, was gezeigt wird.

REGELN:
- Umlaute normal: ä, ö, ü, Ä, Ö, Ü
- ss statt ß (kein ß)
- Sprache: Deutsch
- Kein 'Link in Bio', kein direkter Verkauf"""


# ── REEL FUNKTIONEN ────────────────────────────────────────────────────────────
def generate_hooks(client, thema, nische, zielgruppe, pain_points, gruppe="A"):
    if gruppe == "A":
        user_msg = f"""Erstelle 8 psychologisch triggernde Instagram Reel Hooks — einen pro Typ.

THEMA: {thema}
NISCHE: {nische}
ZIELGRUPPE: {zielgruppe}
PAIN POINTS: {pain_points}

Erstelle EINEN Hook für jeden der folgenden 8 Typen aus Gruppe A — in genau dieser Reihenfolge:
1. INSIDER-VERRAT
2. SCHOCK-ERGEBNIS
3. STILLE-KATASTROPHE
4. WARUM-GEHEIMNIS
5. KONTRA-INTUITION
6. EXPERTEN-ZITAT
7. WENN-DANN-WARNUNG
8. ZAHLEN-SCHOCK

Jeder Hook ist für den Bildtext im Reel – maximal 2-3 Zeilen, gross gedacht.
Jeder Hook muss sofort stoppen, triggern, neugierig machen.
Zeig den Widerspruch oder die Bedrohung → nenn eine Zahl oder ein konkretes Detail → lass die Antwort offen.

ABSOLUT VERBOTEN im Hook:
- Die Lösung nennen
- Die Antwort verraten
- Tipps oder Ratschläge geben
Der Hook zeigt nur Problem, Schmerz oder Neugier-Lücke — nie die Auflösung.

Format exakt so:

HOOK 1 | INSIDER-VERRAT
[Hook-Text]

HOOK 2 | SCHOCK-ERGEBNIS
[Hook-Text]

HOOK 3 | STILLE-KATASTROPHE
[Hook-Text]

HOOK 4 | WARUM-GEHEIMNIS
[Hook-Text]

HOOK 5 | KONTRA-INTUITION
[Hook-Text]

HOOK 6 | EXPERTEN-ZITAT
[Hook-Text]

HOOK 7 | WENN-DANN-WARNUNG
[Hook-Text]

HOOK 8 | ZAHLEN-SCHOCK
[Hook-Text]"""
    else:
        user_msg = f"""Erstelle 5 psychologisch triggernde Instagram Reel Hooks — einen pro Typ.

THEMA: {thema}
NISCHE: {nische}
ZIELGRUPPE: {zielgruppe}
PAIN POINTS: {pain_points}

Erstelle EINEN Hook für jeden der folgenden 5 Typen aus Gruppe B — in genau dieser Reihenfolge:
1. DAS-KLINGT-FALSCH
2. DREI-DINGE
3. ICH-DACHTE
4. NICHT-GLAUBEN
5. DU-MACHST-ES-FALSCH

Wende für jeden Hook das GESETZ DES STARKEN HOOKS an:
- DIE LÜCKE: Problem, Schmerz, Widerspruch — die Person erkennt sich
- DER ERGEBNIS-HINT: konkreter Hinweis WAS sie bekommt — nie die volle Lösung, aber immer eine Richtung

PFLICHT-FORMEL — wähle eine pro Hook:
A) "...ich zeig dir die [Zahl] [Was] — danach [konkretes Ergebnis]."
B) "...welche [Zahl] [Was] das sind — und wie ich sie in [Zeitraum] aufgelöst hab."
C) "[konkreter stuck-point mit Zahl] obwohl sie [tägliche Handlung]."

VERBOTEN: vage Enden / Fragen am Ende / abstrakte Verluste (nie "tausende Euro", immer "bis zu 30.000€")

Format exakt so:

HOOK 1 | DAS-KLINGT-FALSCH
[Hook-Text]

HOOK 2 | DREI-DINGE
[Hook-Text]

HOOK 3 | ICH-DACHTE
[Hook-Text]

HOOK 4 | NICHT-GLAUBEN
[Hook-Text]

HOOK 5 | DU-MACHST-ES-FALSCH
[Hook-Text]"""

    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1800,
        system=SYSTEM_REEL,
        messages=[{"role": "user", "content": user_msg}]
    )
    return r.content[0].text


def generate_caption(client, hook, thema, nische, zielgruppe, pain_points, codewort, cta_ziel, handle):
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_REEL,
        messages=[{"role": "user", "content": f"""Erstelle eine vollständige Instagram Reel Caption basierend auf diesem Hook:

HOOK: {hook}
THEMA: {thema}
NISCHE: {nische}
ZIELGRUPPE: {zielgruppe}
PAIN POINTS: {pain_points}
CODE-WORT: {codewort}
CTA-ZIEL: {cta_ziel}
HANDLE: @{handle}

WICHTIG: Der Hook steht bereits als Bildtext im Video — er wird in der Caption NICHT wiederholt.
Die Caption beginnt direkt mit 1️⃣ und treibt die Neugier weiter — aus einem neuen Winkel.

Struktur der Caption — GENAU so formatieren:

1️⃣ [Kontra-intuitive Eröffnung – anderer Einstieg als der Hook, Problem neu framen, Falsch-Annahme benennen]

2️⃣ [Insider-Anekdote oder Experten-Aussage – konkret, mit Quelle]

3️⃣ [Wissenschaft / Psychologie / Studie – Zahlen oder Fachbegriff]

4️⃣ [Die Lösung / der Trick – konkret und sofort anwendbar]

5️⃣ [Emotionaler Abschluss – Übertragung auf den Leser, letzter Satz bleibt]

[Leerzeile]
[Follow-Satz, lebendig formuliert, Variation von: "Wenn dir das hilft – folge @{handle}. Ich teile solche Einblicke regelmässig."]

[Leerzeile]
Schreib '{codewort}' in die Kommentare – ich schicke dir {cta_ziel} direkt ins Postfach.

WICHTIG:
- Keine Sterne (*) irgendwo im Text
- Keine Markdown-Formatierung
- Keine eckigen Klammern im Output
- Nur die Emoji-Zahlen als Aufzählungszeichen
- Jeder Abschnitt mit Leerzeile getrennt
- Direkt kopierbereit"""}]
    )
    return r.content[0].text


def parse_hooks(text):
    hooks = []
    current_label = ""
    current_text  = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("HOOK ") and "|" in line:
            if current_label and current_text:
                hooks.append({"label": current_label, "text": "\n".join(current_text).strip()})
            parts = line.split("|", 1)
            current_label = parts[1].strip() if len(parts) > 1 else line
            current_text  = []
        elif line and current_label:
            current_text.append(line)
    if current_label and current_text:
        hooks.append({"label": current_label, "text": "\n".join(current_text).strip()})
    return hooks


# ── STORY FUNKTIONEN ───────────────────────────────────────────────────────────
def generate_story(client, situation, nische, zielgruppe, codewort, cta_ziel, handle):
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_STORY,
        messages=[{"role": "user", "content": f"""Erstelle eine vollständige Instagram Story-Sequenz nach Julia Trost Storytelling.

ALLTAGSSITUATION / VIDEO-INHALT:
{situation}

NISCHE: {nische}
ZIELGRUPPE: {zielgruppe}
CODE-WORT: {codewort}
CTA-ZIEL: {cta_ziel}
HANDLE: @{handle}

Erstelle 4 Story-Frames. Format exakt so:

===SITUATION===
[Story Frame 1-2: Die Alltagsszene. Filmisch, nah, konkret. So als wäre die Person dabei.
Maximal 3-4 kurze Sätze. Keine Erklärung – nur zeigen.]

===LEARNING===
[Story Frame 3: Die Erkenntnis, die in dieser Situation steckt.
Überraschend. Tief. Nicht offensichtlich. 2-3 Sätze.]

===BRIDGE===
[Story Frame 4: Die Überleitung zur Zielgruppe.
Was hat das mit ihr zu tun? Direkt ansprechen. 2-3 Sätze.]

===CTA===
[Letzter Frame: Code-Wort + was die Person bekommt.
Format: Schreib "{codewort}" in die Kommentare – [was sie bekommt].
Dazu: Folge @{handle} für mehr solche Einblicke.]"""}]
    )
    return r.content[0].text


def parse_story(text):
    sections = {"situation": "", "learning": "", "bridge": "", "cta": ""}
    current  = None
    lines    = []
    for line in text.splitlines():
        if "===SITUATION===" in line:
            current = "situation"; lines = []
        elif "===LEARNING===" in line:
            sections["situation"] = "\n".join(lines).strip(); current = "learning"; lines = []
        elif "===BRIDGE===" in line:
            sections["learning"] = "\n".join(lines).strip(); current = "bridge"; lines = []
        elif "===CTA===" in line:
            sections["bridge"] = "\n".join(lines).strip(); current = "cta"; lines = []
        elif current:
            lines.append(line)
    if current == "cta":
        sections["cta"] = "\n".join(lines).strip()
    return sections


# ── SESSION STATE ──────────────────────────────────────────────────────────────
defaults = {
    "logged_in": False,
    "user_name": "",
    "user_email": "",
    "mode": None,
    "reel_step": 1, "hook_gruppe": "A", "hooks": [], "hooks_raw": "",
    "selected_hook": "", "caption": "",
    "thema": "", "nische": "", "zielgruppe": "", "pain_points": "",
    "codewort": "", "cta_ziel": "", "handle": "CorinneFurch",
    "story_step": 1, "situation": "", "story_raw": "", "story_sections": {},
    "s_nische": "", "s_zielgruppe": "", "s_codewort": "", "s_cta_ziel": "", "s_handle": "CorinneFurch",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── HEADER & FOOTER ────────────────────────────────────────────────────────────
def render_header():
    if HEADER_IMG.exists():
        img_b64 = base64.b64encode(HEADER_IMG.read_bytes()).decode()
        st.markdown(
            f'<div style="width:100%;border-radius:10px;overflow:hidden;margin-bottom:1rem;">'
            f'<img src="data:image/jpeg;base64,{img_b64}" style="width:100%;display:block;"></div>',
            unsafe_allow_html=True
        )
    st.markdown('<div class="app-title">ELARA Content Creator</div>', unsafe_allow_html=True)


def footer():
    st.markdown(
        '<div class="footer-copy">Copyright Corinne Furch Business Mentoring | Feminine Business CODE® – Geschützte Marke</div>',
        unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN: LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def screen_login():
    render_header()
    st.markdown('<div class="app-sub">Erstelle virale Reel Hooks & Story-Texte in Minuten.</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### Zugang")

    with st.form("login_form"):
        name  = st.text_input("Wie heisst du?", placeholder="Dein Vorname")
        email = st.text_input("Deine E-Mail-Adresse", placeholder="deine@email.com")
        code  = st.text_input("Code")
        submitted = st.form_submit_button("Starten →", use_container_width=True)

    st.markdown(
        '<div class="login-box">Du bist Mitglied der Diamond Mindset Academy. '
        'Dann hast du einen Code bekommen für den kostenlosen Zugriff.</div>',
        unsafe_allow_html=True
    )

    if submitted:
        name  = name.strip()
        email = email.strip().lower()
        code  = code.strip()

        if not name:
            st.error("Bitte gib deinen Vornamen ein.")
            st.stop()
        if not email:
            st.error("Bitte gib deine E-Mail-Adresse ein.")
            st.stop()

        email_ok = check_email_access(email)
        code_ok  = False
        code_msg = ""
        if code:
            code_ok, code_msg = check_code(code)

        if not email_ok and not code_ok:
            if code and not code_ok:
                st.error(code_msg)
            else:
                st.error("Kein gültiger Zugang. Bitte gib deinen Code ein.")
            st.stop()

        st.session_state["logged_in"]  = True
        st.session_state["user_name"]  = name
        st.session_state["user_email"] = email
        st.rerun()

    st.markdown(
        '<div class="hint">Noch kein Code? Infos: <strong>info@corinnefurch.com</strong></div>',
        unsafe_allow_html=True
    )
    footer()


# ── LOGIN CHECK ────────────────────────────────────────────────────────────────
if not st.session_state["logged_in"]:
    screen_login()
    st.stop()

# ── API CHECK ──────────────────────────────────────────────────────────────────
client = get_client()
if not client:
    render_header()
    st.error("API Key fehlt. Bitte in den Streamlit Secrets hinterlegen: ANTHROPIC_API_KEY")
    st.stop()


# ── APP HEADER ─────────────────────────────────────────────────────────────────
render_header()
st.markdown(f'<div class="app-sub">Hallo {st.session_state["user_name"]} 👋</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"**{st.session_state['user_name']}**")
    st.caption(st.session_state["user_email"])
    st.markdown("---")
    if st.button("Abmelden"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# MODE SELECTOR
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["mode"] is None:
    st.markdown("### Was möchtest du heute erstellen?")
    st.markdown("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎬  Reel\nHook + Caption", use_container_width=True):
            st.session_state["mode"] = "reel"
            st.rerun()
    with col2:
        if st.button("📱  Story\nStorytelling nach Julia Trost", use_container_width=True):
            st.session_state["mode"] = "story"
            st.rerun()
    st.stop()

mode_label = "🎬 Reel-Modus" if st.session_state["mode"] == "reel" else "📱 Story-Modus"
if st.button(f"← Modus wechseln  ({mode_label})", key="switch_mode"):
    st.session_state["mode"] = None
    st.rerun()
st.markdown("")


# ══════════════════════════════════════════════════════════════════════════════
# REEL MODUS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["mode"] == "reel":

    if st.session_state["reel_step"] == 1:
        st.markdown('<span class="step-badge">Schritt 1</span> **Thema & Zielgruppe**', unsafe_allow_html=True)
        st.markdown("")

        thema = st.text_input("Thema des Reels", value=st.session_state["thema"],
            placeholder="z.B. Warum Frauen ab 40 finanziell stagnieren")

        col1, col2 = st.columns(2)
        with col1:
            nische = st.text_input("Nische / Positionierung", value=st.session_state["nische"],
                placeholder="z.B. Business-Coaching für Frauen 45+")
        with col2:
            zielgruppe = st.text_input("Zielgruppe", value=st.session_state["zielgruppe"],
                placeholder="z.B. Selbständige Frauen 45+")

        handle = st.text_input("Instagram Handle (ohne @)", value=st.session_state.get("handle", "CorinneFurch"))

        st.markdown("**Pain Points**")
        pain_col1, pain_col2 = st.columns([3, 1])
        with pain_col1:
            pain_points = st.text_area("Pain Points", value=st.session_state["pain_points"],
                placeholder="z.B.\n- Frauen arbeiten mehr, verdienen gleich wenig",
                height=120, label_visibility="collapsed")
        with pain_col2:
            st.markdown(""); st.markdown("")
            if st.button("KI generiert"):
                if thema and nische and zielgruppe:
                    with st.spinner("..."):
                        r = client.messages.create(
                            model="claude-sonnet-4-6", max_tokens=500, system=SYSTEM_REEL,
                            messages=[{"role": "user", "content": f"Generiere 6 starke Pain Points für:\nNische: {nische}\nZielgruppe: {zielgruppe}\nThema: {thema}\nNummerierte Liste, je 1 Satz."}]
                        )
                        st.session_state["pain_points"] = r.content[0].text
                        st.rerun()
                else:
                    st.warning("Erst Thema, Nische und Zielgruppe ausfüllen.")

        st.markdown("---")
        st.markdown("**Hook-Gruppe**")
        gruppe = st.radio(
            "Hook-Gruppe wählen",
            options=["A", "B"],
            format_func=lambda x: "Gruppe A — Klassische Lücken-Hooks (8 Typen)" if x == "A" else "Gruppe B — Widerspruch & Versprechen (5 Typen)",
            index=0 if st.session_state["hook_gruppe"] == "A" else 1,
            horizontal=True,
            label_visibility="collapsed"
        )
        st.session_state["hook_gruppe"] = gruppe

        anzahl = 8 if gruppe == "A" else 5
        if st.button(f"🪝 {anzahl} Hooks generieren (Gruppe {gruppe})"):
            if not all([thema, nische, zielgruppe, pain_points]):
                st.error("Alle Felder sind Pflicht.")
            else:
                st.session_state.update({"thema": thema, "nische": nische,
                    "zielgruppe": zielgruppe, "pain_points": pain_points, "handle": handle})
                with st.spinner(f"Generiere {anzahl} Hooks für Gruppe {gruppe}..."):
                    raw = generate_hooks(client, thema, nische, zielgruppe, pain_points, gruppe)
                    st.session_state["hooks"]     = parse_hooks(raw)
                    st.session_state["reel_step"] = 2
                    st.rerun()

    elif st.session_state["reel_step"] == 2:
        st.markdown('<span class="step-badge">Schritt 2</span> **Hook auswählen**', unsafe_allow_html=True)
        st.caption(f"Thema: {st.session_state['thema']}")
        st.markdown("")

        hooks = st.session_state["hooks"]
        if not hooks:
            st.error("Keine Hooks gefunden.")
        else:
            selected = st.radio("Hook wählen:", options=range(len(hooks)),
                format_func=lambda i: f"Hook {i+1} — {hooks[i]['label']}",
                label_visibility="collapsed")
            st.markdown("")
            st.info(hooks[selected]["text"])

            st.markdown("---")
            st.markdown('<span class="step-badge">Schritt 3</span> **CTA einrichten**', unsafe_allow_html=True)
            st.markdown("")

            col1, col2 = st.columns(2)
            with col1:
                codewort = st.text_input("Code-Wort", value=st.session_state["codewort"], placeholder="z.B. CLARITY")
            with col2:
                cta_ziel = st.text_input("Was bekommt die Person?", value=st.session_state["cta_ziel"],
                    placeholder="z.B. meine kostenlose Checkliste")

            st.markdown("---")
            col_gen, col_back = st.columns([3, 1])
            with col_gen:
                if st.button("✍️ Caption generieren"):
                    if not codewort or not cta_ziel:
                        st.error("Code-Wort und CTA-Ziel sind Pflicht.")
                    else:
                        st.session_state.update({"selected_hook": hooks[selected]["text"],
                            "codewort": codewort, "cta_ziel": cta_ziel})
                        with st.spinner("Schreibe Caption..."):
                            st.session_state["caption"] = generate_caption(
                                client, hooks[selected]["text"],
                                st.session_state["thema"], st.session_state["nische"],
                                st.session_state["zielgruppe"], st.session_state["pain_points"],
                                codewort, cta_ziel, st.session_state["handle"])
                            st.session_state["reel_step"] = 3
                            st.rerun()
            with col_back:
                if st.button("← Zurück"):
                    st.session_state["reel_step"] = 1
                    st.rerun()

    elif st.session_state["reel_step"] == 3:
        st.markdown('<span class="step-badge">Fertig</span> **Dein Reel Content**', unsafe_allow_html=True)
        st.markdown("")

        st.markdown("**Hook** *(Bildtext im Reel)*")
        st.info(st.session_state["selected_hook"])

        st.markdown("**Caption**")
        st.text_area("Caption", value=st.session_state["caption"], height=450, label_visibility="collapsed")

        col1, col2, col3 = st.columns(3)
        with col1:
            caption_bytes = st.session_state["caption"].encode("utf-8")
            st.download_button("⬇ Herunterladen", data=caption_bytes,
                file_name=f"reel-{st.session_state['thema'][:20]}.txt", mime="text/plain")
        with col2:
            if st.button("🔄 Neue Caption"):
                with st.spinner("..."):
                    st.session_state["caption"] = generate_caption(
                        client, st.session_state["selected_hook"],
                        st.session_state["thema"], st.session_state["nische"],
                        st.session_state["zielgruppe"], st.session_state["pain_points"],
                        st.session_state["codewort"], st.session_state["cta_ziel"],
                        st.session_state["handle"])
                    st.rerun()
        with col3:
            if st.button("← Anderen Hook"):
                st.session_state["reel_step"] = 2
                st.session_state["caption"]   = ""
                st.rerun()

        st.markdown("---")
        if st.button("🆕 Neu starten"):
            for k in ["reel_step", "hooks", "selected_hook", "caption", "thema",
                      "nische", "zielgruppe", "pain_points", "codewort", "cta_ziel"]:
                st.session_state[k] = defaults[k]
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STORY MODUS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state["mode"] == "story":

    if st.session_state["story_step"] == 1:
        st.markdown('<span class="step-badge">Schritt 1</span> **Deine Alltagssituation**', unsafe_allow_html=True)
        st.markdown("")

        situation = st.text_area(
            "Was ist passiert? Beschreib die Szene.",
            value=st.session_state["situation"],
            placeholder="z.B. Ich sass heute Morgen mit meinem Kaffee am Küchentisch...",
            height=160
        )

        col1, col2 = st.columns(2)
        with col1:
            s_nische = st.text_input("Nische / Positionierung", value=st.session_state["s_nische"],
                placeholder="z.B. Business-Coaching für Frauen 45+")
        with col2:
            s_zielgruppe = st.text_input("Zielgruppe", value=st.session_state["s_zielgruppe"],
                placeholder="z.B. Selbständige Frauen 45+")

        s_handle = st.text_input("Instagram Handle (ohne @)", value=st.session_state.get("s_handle", "CorinneFurch"))

        st.markdown("---")
        st.markdown('<span class="step-badge">Schritt 2</span> **CTA definieren**', unsafe_allow_html=True)
        st.markdown("")

        col1, col2 = st.columns(2)
        with col1:
            s_codewort = st.text_input("Code-Wort", value=st.session_state["s_codewort"], placeholder="z.B. CLARITY")
        with col2:
            s_cta_ziel = st.text_input("Was bekommt die Person?", value=st.session_state["s_cta_ziel"],
                placeholder="z.B. meine kostenlose Checkliste")

        st.markdown("---")
        if st.button("📱 Story generieren"):
            if not all([situation, s_nische, s_zielgruppe, s_codewort, s_cta_ziel]):
                st.error("Alle Felder sind Pflicht.")
            else:
                st.session_state.update({
                    "situation": situation, "s_nische": s_nische,
                    "s_zielgruppe": s_zielgruppe, "s_handle": s_handle,
                    "s_codewort": s_codewort, "s_cta_ziel": s_cta_ziel
                })
                with st.spinner("Schreibe deine Story..."):
                    raw = generate_story(client, situation, s_nische, s_zielgruppe,
                                         s_codewort, s_cta_ziel, s_handle)
                    st.session_state["story_raw"]      = raw
                    st.session_state["story_sections"] = parse_story(raw)
                    st.session_state["story_step"]     = 2
                    st.rerun()

    elif st.session_state["story_step"] == 2:
        st.markdown('<span class="step-badge">Fertig</span> **Deine Story-Texte**', unsafe_allow_html=True)
        st.markdown("")

        sections = st.session_state["story_sections"]

        if sections.get("situation"):
            st.markdown("**📍 Situation** *(Frame 1–2)*")
            st.markdown(f'<div class="story-frame">{sections["situation"]}</div>', unsafe_allow_html=True)
        if sections.get("learning"):
            st.markdown("**💡 Learning** *(Frame 3)*")
            st.markdown(f'<div class="story-frame">{sections["learning"]}</div>', unsafe_allow_html=True)
        if sections.get("bridge"):
            st.markdown("**🌉 Bridge** *(Frame 4)*")
            st.markdown(f'<div class="story-frame">{sections["bridge"]}</div>', unsafe_allow_html=True)
        if sections.get("cta"):
            st.markdown("**📣 CTA** *(Letzter Frame)*")
            st.markdown(f'<div class="story-frame">{sections["cta"]}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**Alle Texte (kopierbereit)**")
        st.text_area("Story", value=st.session_state["story_raw"], height=400, label_visibility="collapsed")

        col1, col2, col3 = st.columns(3)
        with col1:
            story_bytes = st.session_state["story_raw"].encode("utf-8")
            st.download_button("⬇ Herunterladen", data=story_bytes,
                file_name="story.txt", mime="text/plain")
        with col2:
            if st.button("🔄 Neue Variante"):
                with st.spinner("..."):
                    raw = generate_story(client,
                        st.session_state["situation"], st.session_state["s_nische"],
                        st.session_state["s_zielgruppe"], st.session_state["s_codewort"],
                        st.session_state["s_cta_ziel"], st.session_state["s_handle"])
                    st.session_state["story_raw"]      = raw
                    st.session_state["story_sections"] = parse_story(raw)
                    st.rerun()
        with col3:
            if st.button("← Situation ändern"):
                st.session_state["story_step"] = 1
                st.rerun()

        st.markdown("---")
        if st.button("🆕 Neu starten"):
            for k in ["story_step", "situation", "story_raw", "story_sections",
                      "s_nische", "s_zielgruppe", "s_codewort", "s_cta_ziel"]:
                st.session_state[k] = defaults[k]
            st.rerun()

footer()

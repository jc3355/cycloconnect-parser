from fastapi import FastAPI, UploadFile, File, HTTPException
from decimal import Decimal, ROUND_HALF_UP
import pdfplumber
import re

app = FastAPI()

def fr_to_decimal(value):
    if value is None:
        return Decimal("0")
    value = value.replace("\xa0", "").replace("€", "").replace(" ", "")
    value = value.replace(",", ".")
    return Decimal(value)

def round2(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def find_amount_required(pattern: str, text: str, label: str) -> Decimal:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        raise HTTPException(status_code=400, detail=f"Impossible de trouver '{label}' dans le PDF.")
    return fr_to_decimal(m.group(1))

def find_amount_optional(pattern: str, text: str) -> Decimal:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return Decimal("0")
    return fr_to_decimal(m.group(1))

def find_amount_any(patterns, text: str, label: str) -> Decimal:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return fr_to_decimal(m.group(1))
    raise HTTPException(status_code=400, detail=f"Impossible de trouver '{label}' dans le PDF.")

@app.post("/parse")
async def parse_pdf(file: UploadFile = File(...)):

    with pdfplumber.open(file.file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # 🔎 TOTAL HT (plusieurs formats possibles)
    total_ht = find_amount_any([
        r"Total\s*HT\s*après\s*prestations\s*offertes[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        r"Total\s*HT[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
    ], text, "Total HT")

    # 🔎 TVA (plusieurs formats possibles)
    total_tva = find_amount_any([
        r"Montant\s*total\s*de\s*la\s*TVA[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        r"TVA[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
    ], text, "TVA")

    # 🔎 TOTAL TTC (plusieurs formats possibles)
    total_ttc = find_amount_any([
        r"Total\s*TTC\s*à\s*payer[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        r"Total\s*TTC[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
    ], text, "Total TTC")

    # 🔎 FRAIS DE SERVICE (optionnel)
    frais_service = find_amount_optional(
        r"Frais\s*de\s*service[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        text
    )

    # 🧮 Calculs
    prestations = total_ht - frais_service

    commission_ht = prestations * Decimal("0.35") + frais_service
    tva_jsmv = commission_ht * Decimal("0.20")

    reversement_reparateur = total_ttc - (commission_ht + tva_jsmv)
    ca_reparateur = prestations * Decimal("0.65")
    tva_reparateur = ca_reparateur * Decimal("0.20")

    return {
        "total_ht": float(round2(total_ht)),
        "total_tva": float(round2(total_tva)),
        "total_ttc": float(round2(total_ttc)),
        "frais_service_ht": float(round2(frais_service)),
        "prestations_ht": float(round2(prestations)),
        "commission_ht": float(round2(commission_ht)),
        "tva_jsmv": float(round2(tva_jsmv)),
        "reversement_reparateur": float(round2(reversement_reparateur)),
        "ca_reparateur": float(round2(ca_reparateur)),
        "tva_reparateur": float(round2(tva_reparateur))
    }

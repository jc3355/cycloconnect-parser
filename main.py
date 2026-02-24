from fastapi import FastAPI, UploadFile, File
from decimal import Decimal
import pdfplumber
import re

app = FastAPI()

def fr_to_decimal(value: str | None) -> Decimal:
    if not value:
        return Decimal("0")
    value = value.replace("\xa0", "").replace("€", "").replace(" ", "")
    value = value.replace(",", ".")
    return Decimal(value)

def extract_first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None

def extract_commande_id(text: str) -> str | None:
    """
    Extrait un id du type Lae-46059-1 / Mor-45800-1 etc.
    On cherche dans tout le texte PDF.
    """
    m = re.search(r"\b([A-Za-z]{3}-\d{5}-\d)\b", text)
    return m.group(1) if m else None

from fastapi import FastAPI
from pydantic import BaseModel
import requests
import io

class ParseRequest(BaseModel):
    file_id: str
    file_name: str | None = None

@app.post("/parse")
async def parse_pdf(req: ParseRequest):

    url = f"https://drive.google.com/uc?export=download&id={req.file_id}"

    response = requests.get(url)
    pdf_bytes = io.BytesIO(response.content)

    with pdfplumber.open(pdf_bytes) as pdf:
        parts = []
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)

    text = "\n".join(parts)
    # 1) Extraire le texte
    with pdfplumber.open(file.file) as pdf:
        parts = []
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    text = "\n".join(parts)

    # 2) Extraire commande_id
    commande_id = extract_commande_id(text)

    # 3) Totaux
    total_ht_raw  = extract_first(r"Total\s*HT\s+([\d\s,]+)", text)
    total_tva_raw = extract_first(r"\bTVA\b\s+([\d\s,]+)", text)
    total_ttc_raw = extract_first(r"Total\s*TTC\s+([\d\s,]+)", text)

    # Frais de service (optionnel)
    frais_service_raw = extract_first(r"Frais\s*de\s*service\s+([\d\s,]+)", text)

    if not total_ht_raw or not total_tva_raw or not total_ttc_raw:
        # Debug utile si jamais un PDF a un format différent
        return {
            "ok": False,
            "error_status": 400,
            "error_body": {
                "detail": "Impossible de trouver Total HT / TVA / Total TTC dans le PDF."
            },
            "debug_excerpt": text[:2500],
        }

    total_ht = fr_to_decimal(total_ht_raw)
    total_tva = fr_to_decimal(total_tva_raw)
    total_ttc = fr_to_decimal(total_ttc_raw)
    frais_service_ht = fr_to_decimal(frais_service_raw)  # 0 si absent

    # 4) Calculs (ta logique actuelle)
    prestations_ht = total_ht - frais_service_ht

    commission_ht = (prestations_ht * Decimal("0.35")) + frais_service_ht
    tva_jsmv = commission_ht * Decimal("0.20")

    reversement_reparateur = total_ttc - (commission_ht + tva_jsmv)
    ca_reparateur = prestations_ht * Decimal("0.65")
    tva_reparateur = ca_reparateur * Decimal("0.20")

    return {
    "ok": True,
    "parsed": {
        "commande_id": commande_id,
        "total_ht": float(total_ht),
        "total_tva": float(total_tva),
        "total_ttc": float(total_ttc),
        "frais_service_ht": float(frais_service_ht),
        "prestations_ht": float(prestations_ht),
        "commission_ht": float(commission_ht),
        "tva_jsmv": float(tva_jsmv),
        "reversement_reparateur": float(reversement_reparateur),
        "ca_reparateur": float(ca_reparateur),
        "tva_reparateur": float(tva_reparateur),
    }
}

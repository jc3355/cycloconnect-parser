from fastapi import FastAPI, UploadFile, File, HTTPException
from decimal import Decimal
import pdfplumber
import re

app = FastAPI()

def fr_to_decimal(value: str) -> Decimal:
    """
    Convertit un nombre FR vers Decimal
    Ex: "1 234,56 €" -> Decimal("1234.56")
    """
    if value is None:
        return Decimal("0")
    value = str(value)
    value = value.replace("\xa0", " ")
    value = value.replace("€", "")
    value = value.replace(" ", "")
    value = value.replace(",", ".")
    value = re.sub(r"[^0-9\.\-]", "", value)
    if value == "":
        return Decimal("0")
    return Decimal(value)

def find_amount_required(pattern: str, text: str, label: str) -> Decimal:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de trouver '{label}' dans le PDF."
        )
    return fr_to_decimal(m.group(1))

def find_amount_optional(pattern: str, text: str) -> Decimal:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return Decimal("0")
    return fr_to_decimal(m.group(1))

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/parse")
async def parse_pdf(file: UploadFile = File(...)):

    with pdfplumber.open(file.file) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
        text = "\n".join(pages)

    # TOTAL HT (ancré sur "Total HT")
    total_ht = find_amount_required(
        r"Total\s*HT[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        text,
        "Total HT"
    )

    # TVA (ancré sur "Montant total de la TVA")
    total_tva = find_amount_required(
        r"Montant\s*total\s*de\s*la\s*TVA[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        text,
        "Montant total de la TVA"
    )

    # TOTAL TTC
    total_ttc = find_amount_required(
        r"Total\s*TTC[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        text,
        "Total TTC"
    )

    # FRAIS DE SERVICE (optionnel -> 0 si absent)
    frais_service_ht = find_amount_optional(
        r"Frais\s*de\s*service[^0-9]*([0-9][0-9\s\xa0]*,[0-9]{2})\s*€?",
        text
    )

    prestations_ht = total_ht - frais_service_ht

    commission_ht = (prestations_ht * Decimal("0.35")) + frais_service_ht
    tva_jsmv = commission_ht * Decimal("0.20")

    reversement_reparateur = total_ttc - (commission_ht + tva_jsmv)
    ca_reparateur = prestations_ht * Decimal("0.65")
    tva_reparateur = ca_reparateur * Decimal("0.20")

    return {
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
        "debug_excerpt": text[:1500]
    }

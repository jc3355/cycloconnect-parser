from fastapi import FastAPI, UploadFile, File
from decimal import Decimal
import pdfplumber
import re

app = FastAPI()

def fr_to_decimal(value):
    if value is None:
        return Decimal("0")
    value = value.replace("\xa0", "").replace("€", "").replace(" ", "")
    value = value.replace(",", ".")
    return Decimal(value)

@app.post("/parse")
async def parse_pdf(file: UploadFile = File(...)):
    
    with pdfplumber.open(file.file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()

    total_ht = re.search(r"Total HT\s+([\d\s,]+)", text)
    total_tva = re.search(r"TVA\s+([\d\s,]+)", text)
    total_ttc = re.search(r"Total TTC\s+([\d\s,]+)", text)
    frais_service = re.search(r"Frais de service\s+([\d\s,]+)", text)

    total_ht = fr_to_decimal(total_ht.group(1))
    total_tva = fr_to_decimal(total_tva.group(1))
    total_ttc = fr_to_decimal(total_ttc.group(1))
    frais_service = fr_to_decimal(frais_service.group(1))

    prestations = total_ht - frais_service

    commission = prestations * Decimal("0.35") + frais_service
    tva_jsmv = commission * Decimal("0.20")

    reversement = total_ttc - (commission + tva_jsmv)
    ca_reparateur = prestations * Decimal("0.65")
    tva_reparateur = ca_reparateur * Decimal("0.20")

    return {
        "total_ht": float(total_ht),
        "total_tva": float(total_tva),
        "total_ttc": float(total_ttc),
        "frais_service": float(frais_service),
        "prestations": float(prestations),
        "commission": float(commission),
        "tva_jsmv": float(tva_jsmv),
        "reversement": float(reversement),
        "ca_reparateur": float(ca_reparateur),
        "tva_reparateur": float(tva_reparateur)
    }

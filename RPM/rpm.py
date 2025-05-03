import requests


def get_patient_data(patient_id):
    #GET Abfrage an den Server mit Patienten ID
    url = f"https://disp.yxl.ch/rpm/patients/{int(patient_id)}"
    print(f"[DEBUG] GET: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def evaluate_status(measurements):
    #Prüfen ob erhaltene O2 Werte unter Vorgabe sind
    spo2_values = [m["spo2"] for m in measurements]
    if any(val < 95 for val in spo2_values):
        return "Warning"
    return "OK"

def send_clinician_message(patient_id, message):
    #übergabe Nachricht an Server
    url = f"https://disp.yxl.ch/rpm/patients/{int(patient_id)}"
    payload = {"message": message}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()
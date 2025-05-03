import sys
import os
from datetime import datetime
from dateutil import parser
from rpm import get_patient_data, evaluate_status, send_clinician_message
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QToolTip,
    QTableWidget, QTableWidgetItem, QTextEdit, QPushButton, QLineEdit, QHBoxLayout
)
from PySide6.QtGui import QIcon, QColor


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

class RPMWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        #Hauptfenster
        self.setWindowTitle("Remote Patient Monitoring")
        icon_path = resource_path("icon.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(800, 600)

        #Temporärer Speicher für ausgewählte Patienten ID
        self.current_patient_id = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        #Statusanzeige im Fenster oben
        self.status_label = QLabel("Status: -")
        self.layout.addWidget(self.status_label)

        #Tabelle im Fenster
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Zeit", "SpO₂"])
        self.layout.addWidget(self.table)

        #Nachrichtenbox für Arzt
        self.message_box = QTextEdit()
        self.message_box.setPlaceholderText("Nachricht an den Patienten...")
        self.layout.addWidget(self.message_box)

        #Send-Button für die Nachricht, funktioniert bewusst nicht mit Enter
        self.send_button = QPushButton("Nachricht senden")
        self.send_button.clicked.connect(self.send_message)
        self.layout.addWidget(self.send_button)

        #Daten-laden-Button für Eingabe PatientenID, funktioniert bewusst mit Enter
        self.load_button = QPushButton("Daten laden")
        self.load_button.clicked.connect(self.on_load_clicked)

        #Eingabefeld PatientenID
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Patienten-ID eingeben")
        self.id_input.returnPressed.connect(self.load_button.click)

        #Horizontales Layout für ID-Eingabefeld und Daten Laden Button
        id_layout = QHBoxLayout()
        id_layout.addWidget(self.id_input)
        id_layout.addWidget(self.load_button)
        self.layout.addLayout(id_layout)

        #Nachrichtenbox standardmässig nicht sichtbar
        self.message_box.setVisible(False)
        self.send_button.setVisible(False)

    def on_load_clicked(self):
        # Holt den eingegebenen Text aus dem ID-Feld
        patient_id_str = self.id_input.text().strip()
        # Prüft, ob die Eingabe eine Zahl ist
        if not patient_id_str.isdigit():
            self.status_label.setText("Ungültige ID.")
            return

        # Umwandlung in Integer und Abspeichern für spätere Verwendung
        patient_id = int(patient_id_str)
        self.current_patient_id = patient_id

        # Daten vom Server laden
        self.load_data(patient_id)

    def load_data(self, patient_id):
        # Versucht Patientendaten vom Server abzurufen
        try:
            data = get_patient_data(patient_id)
        except Exception as e:
            # Prüft, ob vom Server ein Fehler mit JSON-Antwort zurückkam
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_json = e.response.json()
                    if error_json.get("error") == "Patient ID not authorised":
                        # UI zurücksetzen und Sprechblase anzeigen
                        self.reset_ui()
                        QToolTip.showText(
                            self.id_input.mapToGlobal(self.id_input.rect().bottomLeft()),
                            "Diese Patienten-ID ist nicht auf dem Server."
                        )
                        return
                except Exception:
                    pass
            # Allgemeine Fehlermeldung anzeigen und UI zurücksetzen
            self.status_label.setText(f"Fehler: {e}")
            self.reset_ui()
            return

        # Messwerte extrahieren
        measurements = data["measurements"]

        # Tabelle aktualisieren
        self.update_table(measurements)

        # Status auswerten und anzeigen
        status = evaluate_status(measurements)
        if status == "Warning":
            self.status_label.setText("Status: Warning")
            self.message_box.setVisible(True)
            self.send_button.setVisible(True)
        else:
            self.status_label.setText("Status: OK")
            self.message_box.setVisible(False)
            self.send_button.setVisible(False)
            self.message_box.clear()

    def update_table(self, measurements):
        # Löscht bestehende Zeilen
        self.table.setRowCount(0)

        # Fügt Messwerte zeilenweise in die Tabelle ein
        for row, m in enumerate(measurements):
            self.table.insertRow(row)

            # Zeitstempel leserlich formatieren
            iso_time = m["timestamp"]
            try:
                dt = parser.isoparse(iso_time)
                formatted_time = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                formatted_time = iso_time  # fallback, falls fehlerhaft

            self.table.setItem(row, 0, QTableWidgetItem(formatted_time))

            # SpO2-Wert anzeigen und ggf. rot markieren
            spo2_value = m["spo2"]
            spo2_item = QTableWidgetItem(str(spo2_value))

            if spo2_value < 95:
                spo2_item.setForeground(QColor("red"))

            self.table.setItem(row, 1, spo2_item)

    def send_message(self):
        # Nachrichtentext aus dem Eingabefeld holen
        message = self.message_box.toPlainText().strip()
        if not message:
            self.status_label.setText("Bitte Nachricht eingeben.")
            return

        # Sicherstellen, dass ein Patient geladen ist
        if self.current_patient_id is None:
            self.status_label.setText("Keine Patientendaten geladen.")
            return

        # Nachricht an den Server senden
        try:
            result = send_clinician_message(self.current_patient_id, message)
            print("[DEBUG] Serverantwort:", result)

            # Erfolgreiches Speichern prüfen
            if (
                result.get("stored") is True and
                result.get("patient_id") == self.current_patient_id and
                result.get("message") == message
            ):
                print("[DEBUG] Nachricht wurde erfolgreich gespeichert.")
                self.status_label.setText("Nachricht gesendet.")
                self.message_box.clear()
            else:
                print("[DEBUG] Unerwartete Serverantwort:", result)
                self.status_label.setText("Antwort unerwartet – siehe Konsole.")
        except Exception as e:
            print(f"[DEBUG] Fehler beim Senden: {e}")
            self.status_label.setText(f"Fehler beim Senden: {e}")

    def reset_ui(self):
        # Setzt das UI in den Ausgangszustand zurück
        self.table.setRowCount(0)
        self.status_label.setText("Status: -")
        self.message_box.clear()
        self.message_box.setVisible(False)
        self.send_button.setVisible(False)
        self.current_patient_id = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RPMWindow()
    window.show()
    sys.exit(app.exec())
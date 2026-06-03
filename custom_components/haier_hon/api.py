import logging
import asyncio
from pyhon import Hon

_LOGGER = logging.getLogger(__name__)

class HonApiClient:
    """Client ufficiale per comunicare con l'API Cloud hOn di Haier tramite pyhOn v0.17.5."""

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._hon = None

    async def get_devices(self):
        """Effettua il login e recupera gli elettrodomestici usando il dizionario .data nativo."""
        try:
            if self._hon is None:
                _LOGGER.info("Inizializzazione autenticazione hOn per l'utente: %s", self._username)
                
                # Nella v0.17.x l'inizializzazione solida richiede i parametri passati esplicitamente
                self._hon = Hon(self._username, self._password, test_mode=False)
                
                # Il setup scarica l'elenco dei dispositivi ed effettua il WebSocket/polling iniziale
                await self._hon.setup()
                _LOGGER.info("Connessione ai server Cloud Haier hOn stabilita con successo.")

            appliances = []
            
            # Controllo di sicurezza sull'esistenza dell'array degli elettrodomestici
            if not hOn_appliances := getattr(self._hon, "appliances", None):
                _LOGGER.warning("Nessun dispositivo associato all'account hOn specificato.")
                return appliances

            for appliance in hOn_appliances:
                # Estraiamo l'ID unico del dispositivo (fondamentale per accoppiarlo alle entità)
                appliance_id = appliance.info.get("applianceId") or getattr(appliance, "id", None)
                if not appliance_id:
                    continue

                # pyhOn v0.17.x memorizza lo stato attuale dei sensori dentro il dizionario appliance.data
                # Usiamo un recupero sicuro con .get() direttamente sul dizionario dei dati reali
                device_raw_data = getattr(appliance, "data", {})

                # Costruiamo la struttura 'shadow' attesa da climate.py e sensor.py dell'integrazione
                appliance_data = {
                    "applianceId": str(appliance_id),
                    "shadow": {
                        "parameters": {
                            "onOffStatus": {"value": int(device_raw_data.get("onOffStatus", 0))},
                            "machMode": {"value": int(device_raw_data.get("machMode", 1))},
                            "tempSel": {"value": float(device_raw_data.get("tempSel", 24.0))},
                            "compressorFrequency": {"value": float(device_raw_data.get("compressorFrequency", 0.0))},
                            "tempIndoor": {"value": float(device_raw_data.get("tempIndoor", 20.0))},
                            "tempOutdoor": {"value": float(device_raw_data.get("tempOutdoor", 20.0))},
                        }
                    }
                }
                appliances.append(appliance_data)
                
            return appliances

        except Exception as err:
            _LOGGER.error("Errore critico definitivo di comunicazione con pyhOn: %s", err)
            raise err

    async def set_device_status(self, appliance_id, parameters: dict):
        """Invia i comandi di controllo modificando le impostazioni dell'appliance."""
        try:
            if self._hon is None:
                _LOGGER.error("Impossibile inviare comandi: la sessione hOn non è inizializzata.")
                return False
                
            for appliance in self._hon.appliances:
                current_id = appliance.info.get("applianceId") or getattr(appliance, "id", None)
                if str(current_id) == str(appliance_id):
                    # In pyhOn i comandi si inviano aggiornando i parametri tramite il metodo nativo dell'oggetto
                    for key, value in parameters.items():
                        if hasattr(appliance, "set_parameter"):
                            await appliance.set_parameter(key, value)
                        elif hasattr(appliance, "parameters") and key in appliance.parameters:
                            await appliance.parameters[key].set_value(value)
                    return True
            return False
        except Exception as err:
            _LOGGER.error("Impossibile inviare il comando al dispositivo %s: %s", appliance_id, err)
            raise err
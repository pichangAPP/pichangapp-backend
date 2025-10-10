from typing import Any, Dict, List, Text
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


class ActionHumanHandoff(Action):
    def name(self) -> Text:
        return "action_human_handoff"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        # Recolectar los últimos mensajes relevantes
        convo: List[str] = []
        for event in tracker.events[-10:]:  # solo los últimos 10 eventos
            if event.get("event") == "user":
                user_text = str(event.get("text") or "")
                convo.append(f"Usuario: {user_text}")
            elif event.get("event") == "bot":
                bot_text = str(event.get("text") or "")
                convo.append(f"Bot: {bot_text}")

        # Generar un resumen básico local
        resumen = "\n".join(convo)
        dispatcher.utter_message(
            text="Te transfiero con un agente humano. Aquí está el resumen de la conversación:"
        )
        dispatcher.utter_message(text=resumen)

        # Aquí podrías agregar lógica para enviar el resumen a un dashboard o a un sistema externo
        return []

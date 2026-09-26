"""
AETHERIS AI — Agent Base Class
All agents inherit from this to share logging + inference access.
"""
import logging
from backend.app.services.inference_gateway import InferenceGateway, get_inference_gateway


class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"aetheris.agent.{name}")
        self._gateway: InferenceGateway | None = None

    @property
    def gateway(self) -> InferenceGateway:
        if self._gateway is None:
            self._gateway = get_inference_gateway()
        return self._gateway

    def _log(self, msg: str) -> None:
        self.logger.info(f"[{self.name}] {msg}")

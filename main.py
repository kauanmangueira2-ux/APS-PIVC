"""Ponto de entrada: sobe a API e o terminal web em http://localhost:8000"""
import uvicorn

import config

if __name__ == "__main__":
    if config.USANDO_SEGREDOS_PADRAO:
        print("AVISO: ADMIN_TOKEN/PIN_PEPPER não definidos — usando valores padrão (inseguros).\n"
              "       Copie .env.example para .env e troque os dois antes de usar de verdade.\n")
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000)

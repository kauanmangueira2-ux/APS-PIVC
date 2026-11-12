# Fluxo do sistema (APS-6)

## Tentativa de acesso (terminal do cofre)

```mermaid
flowchart TD
    A([Pessoa diante do terminal]) --> B[Escolhe o recurso]
    B --> C{Terminal bloqueado?<br/>3 negativas seguidas em até 60 s,<br/>bloqueio de 60 s desde a última}
    C -- sim --> C1[/Mensagem: aguarde Ns/]
    C -- não --> D[Captura quadro<br/>nível 3: rajada de 15 quadros + PIN]
    D --> E[Fase 2: CLAHE + filtro bilateral]
    E --> F{Fases 3–4:<br/>um rosto nítido e próximo?}
    F -- não --> F1[/Erro orientando: sem rosto, vários rostos,<br/>longe, escuro, pouco nítido/]
    F -- sim --> G[Fase 4: vetor ArcFace 512 d]
    G --> H[Fase 5: cosseno contra a galeria]
    H --> I{score ≥ limiar 0,40<br/>e vence a 2ª pessoa por 0,05?}
    I -- não --> N1[(Log: nao_reconhecido + evidência)]
    I -- sim --> J{Nível do usuário ≥ nível do recurso?}
    J -- não --> N2[(Log: negado_nivel + evidência)]
    J -- sim --> K{Nível 2: divisão do recurso é a dele?}
    K -- não --> N3[(Log: negado_divisao + evidência)]
    K -- sim --> L{Nível 2 em acervo: dentro do expediente?<br/>antessala/catálogo não têm horário}
    L -- não --> N4[(Log: negado_horario + evidência)]
    L -- sim --> M{Recurso de nível 3?}
    M -- não --> OK[(Log: concedido)]
    M -- sim --> P{Piscou? EAR relativo<br/>um só rosto e a mesma pessoa?}
    P -- não --> N5[(Log: falha_liveness + evidência + alerta)]
    P -- sim --> B3{3 PINs errados<br/>nos últimos 15 min?}
    B3 -- sim --> N7[(Log: pin_bloqueado + evidência + alerta)]
    B3 -- não --> Q{PIN correto?}
    Q -- não --> N6[(Log: pin_invalido + evidência + alerta)]
    Q -- sim --> OK
    OK --> Z([Acesso concedido])
    N1 & N2 & N3 & N4 & N5 & N6 & N7 --> Y([Acesso negado])
```

## Módulos e contratos

| Módulo | Entrada | Saída |
|---|---|---|
| `visao/` | quadro BGR | `Resultado(vetor float32[512], bbox, qualidade)` ou `ErroVisao` |
| `core/matcher.py` | vetor | `(usuario_id \| None, score)` |
| `core/permissoes.py` | usuário, recurso, hora | `(concedido, motivo)` |
| `core/fluxo.py` | imagens, recurso, PIN | resposta JSON + registro em `acessos` |
| `api/app.py` | HTTP | JSON / CSV / PDF |
| `web/` | — | terminal, cadastro, pessoas, logs |

## Rotas da API

| Rota | Quem | Tarefa |
|---|---|---|
| `GET /api/recursos` | terminal | APS-12 |
| `POST /api/reconhecer` | terminal | APS-16 |
| `POST /api/usuarios` · `POST /api/usuarios/{id}/biometrias` | admin | APS-15 |
| `GET/PUT/DELETE /api/usuarios` | admin | APS-19 |
| `GET /api/logs` · `GET /api/alertas` · `GET /api/evidencia/{arq}` | admin | APS-18 |
| `GET /api/logs/exportar?formato=csv\|pdf` | admin | APS-19 |
| `POST /api/qualidade` · `GET /api/resumo` · `GET /api/saude` | admin / público | melhorias |

## Protótipos (APS-7 e APS-8)

Terminal: vídeo ao vivo, seletor de recurso, campo de PIN (só no nível 3), botão **Autenticar**, painel verde/vermelho com nome, nível e score.

Admin: **Cadastro** (formulário + captura de 3–5 fotos), **Pessoas** (tabela com nível, divisão, ativar/desativar, remover), **Logs** (filtros, alerta, exportar CSV/PDF). As telas implementadas em `web/` são o protótipo funcional.

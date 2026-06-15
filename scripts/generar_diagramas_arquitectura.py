"""Genera diagramas PNG de la arquitectura distribuida del CRM."""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

# Paleta
C_CLIENT = "#E3F2FD"
C_WEB = "#E8F5E9"
C_WORKER = "#FFF3E0"
C_AGENTS = "#F3E5F5"
C_INFRA = "#ECEFF1"
C_BORDER = "#37474F"
C_ARROW = "#546E7A"
C_TEXT = "#263238"


def _box(ax, x, y, w, h, text, facecolor, fontsize=9, bold_title=None):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.5, edgecolor=C_BORDER, facecolor=facecolor,
    )
    ax.add_patch(patch)
    if bold_title:
        ax.text(x + w / 2, y + h - 0.35, bold_title, ha="center", va="top",
                fontsize=10, fontweight="bold", color=C_TEXT)
        ax.text(x + w / 2, y + h / 2 - 0.15, text, ha="center", va="center",
                fontsize=fontsize, color=C_TEXT, linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, color=C_TEXT, linespacing=1.35)


def _cylinder(ax, x, y, w, h, text, facecolor):
    body = FancyBboxPatch(
        (x, y), w, h * 0.85,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.5, edgecolor=C_BORDER, facecolor=facecolor,
    )
    ax.add_patch(body)
    top = mpatches.Ellipse((x + w / 2, y + h * 0.85), w, h * 0.18,
                           linewidth=1.5, edgecolor=C_BORDER, facecolor=facecolor)
    ax.add_patch(top)
    ax.text(x + w / 2, y + h * 0.42, text, ha="center", va="center",
            fontsize=9, color=C_TEXT, linespacing=1.3)


def _arrow(ax, x1, y1, x2, y2, label=None, style="-|>", rad=0.0):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, color=C_ARROW, linewidth=1.4,
        connectionstyle=f"arc3,rad={rad}",
        mutation_scale=12,
    )
    ax.add_patch(arr)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.15, label, ha="center", va="bottom",
                fontsize=7, color=C_ARROW, style="italic",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.85))


def diagrama_arquitectura_general():
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("CRM Orbes — Arquitectura Distribuida", fontsize=16, fontweight="bold", pad=16, color=C_TEXT)

    # Cliente
    _box(ax, 0.5, 8.5, 3.2, 2.0, "UI Jinja2 + JS\nSocket.IO Monitor", C_CLIENT,
         bold_title="Cliente / Navegador")

    # Web
    _box(ax, 5.0, 7.8, 4.5, 2.8,
         "app.py / Flask\nRoutes: auth · crm · marketing · agents\nFlask-SocketIO",
         C_WEB, bold_title="Servicio Web  :8000")

    # Worker
    _box(ax, 5.0, 4.5, 4.5, 2.5,
         "process_lead_task\nOrquestador de grafo\n(Celery Worker)",
         C_WORKER, bold_title="Workflow Worker")

    # Agent services
    _box(ax, 10.5, 4.5, 4.8, 2.5,
         "REST /agents/*\nScoring · Commercial\nRecovery · Closing",
         C_AGENTS, bold_title="Microservicio Agentes  :8001")

    # Infra
    _cylinder(ax, 5.5, 0.8, 2.2, 2.0, "Redis\ncola + bus\nSocket.IO", C_INFRA)
    _cylinder(ax, 9.0, 0.8, 2.5, 2.0, "MySQL CRM\nlead_agent_state\nagent_interactions", C_INFRA)
    ax.text(8.3, 0.35, "Infraestructura compartida", ha="center", fontsize=10,
            fontweight="bold", color=C_TEXT)

    # Flechas
    _arrow(ax, 3.7, 9.2, 5.0, 9.2, "HTTP")
    _arrow(ax, 3.7, 9.8, 5.0, 9.0, "WebSocket", rad=0.1)
    _arrow(ax, 7.2, 7.8, 7.2, 7.0, "encolar lead")
    _arrow(ax, 7.2, 4.5, 7.2, 3.6, "cola workflow")
    _arrow(ax, 9.5, 5.8, 10.5, 5.8, "HTTP POST")
    _arrow(ax, 6.6, 4.5, 6.6, 2.8, "SQL")
    _arrow(ax, 10.2, 4.5, 10.2, 2.8, "SQL")
    _arrow(ax, 7.2, 7.8, 9.5, 2.8, "SQL", rad=-0.15)
    _arrow(ax, 8.5, 5.5, 8.5, 7.8, "eventos vía Redis MQ", rad=0.2)

    # Leyenda
    legend_items = [
        mpatches.Patch(facecolor=C_WEB, edgecolor=C_BORDER, label="Proceso Python desplegable"),
        mpatches.Patch(facecolor=C_INFRA, edgecolor=C_BORDER, label="Servicio de infraestructura"),
    ]
    ax.legend(handles=legend_items, loc="upper right", fontsize=9, framealpha=0.95)

    fig.tight_layout()
    path = OUT / "arquitectura_distribuida_general.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def diagrama_flujo_lead():
    fig, ax = plt.subplots(figsize=(15, 10))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Flujo de Lead Nuevo — Workflow Multiagente", fontsize=16, fontweight="bold", pad=16, color=C_TEXT)

    participants = [
        ("Usuario\nCRM", 0.8, C_CLIENT),
        ("Web\n:8000", 3.2, C_WEB),
        ("Redis", 5.6, C_INFRA),
        ("Celery\nWorker", 8.0, C_WORKER),
        ("Agent\nServices :8001", 10.4, C_AGENTS),
        ("MySQL", 12.8, C_INFRA),
    ]
    py = 9.0
    for name, px, color in participants:
        _box(ax, px - 0.7, py - 0.5, 1.4, 1.0, name, color, fontsize=8)

    steps = [
        (0.8, 3.2, "1. Crear lead"),
        (3.2, 12.8, "2. INSERT lead"),
        (3.2, 5.6, "3. Encolar tarea"),
        (3.2, 0.8, "4. Redirect async"),
        (5.6, 8.0, "5. Consume tarea"),
        (8.0, 10.4, "6. POST /scoring/analyze"),
        (10.4, 12.8, "7. log_interaction"),
        (10.4, 8.0, "8. score + prioridad"),
        (8.0, 10.4, "9. POST /commercial/assign"),
        (8.0, 10.4, "10. POST /commercial/contact"),
    ]

    y_start = 8.2
    messages = [
        (0.8, 3.2, "POST /leads/create", y_start),
        (3.2, 12.8, "INSERT lead", y_start - 0.7),
        (3.2, 5.6, "LPUSH process_lead_task", y_start - 1.4),
        (3.2, 0.8, "302 redirect", y_start - 2.1, True),
        (5.6, 8.0, "consume tarea", y_start - 2.8),
        (8.0, 3.2, "workflow_async_started", y_start - 3.5, True),
        (8.0, 10.4, "POST /agents/scoring/analyze", y_start - 4.2),
        (10.4, 12.8, "log_interaction", y_start - 4.9),
        (10.4, 8.0, "score + prioridad", y_start - 5.6, True),
        (8.0, 10.4, "POST /commercial/assign", y_start - 6.3),
        (8.0, 10.4, "POST /commercial/contact", y_start - 7.0),
    ]

    for item in messages:
        x1, x2, label, y = item[0], item[1], item[2], item[3]
        dashed = item[4] if len(item) > 4 else False
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="-|>", color=C_ARROW, lw=1.2,
                                    linestyle="dashed" if dashed else "solid"))
        ax.text((x1 + x2) / 2, y + 0.12, label, ha="center", va="bottom", fontsize=7.5, color=C_TEXT)

    # Rama condicional
    branch_y = 1.8
    ax.text(7.5, branch_y + 1.0, "¿Cliente responde?", ha="center", fontsize=9,
            fontweight="bold", color=C_TEXT,
            bbox=dict(boxstyle="round", facecolor="#FFFDE7", edgecolor=C_BORDER))
    _arrow(ax, 8.0, branch_y + 0.7, 10.4, branch_y + 0.7, "Sí → POST /closing/run")
    _arrow(ax, 8.0, branch_y + 0.3, 10.4, branch_y + 0.3, "No → POST /recovery/attempt", rad=0.0)

    ax.annotate("", xy=(12.8, branch_y - 0.5), xytext=(8.0, branch_y - 0.5),
                arrowprops=dict(arrowstyle="-|>", color=C_ARROW, lw=1.2))
    ax.text(10.4, branch_y - 0.35, "actualizar lead_agent_state", ha="center", fontsize=7.5, color=C_TEXT)

    ax.annotate("", xy=(3.2, branch_y - 1.2), xytext=(8.0, branch_y - 1.2),
                arrowprops=dict(arrowstyle="-|>", color=C_ARROW, lw=1.2, linestyle="dashed"))
    ax.text(5.6, branch_y - 1.0, "workflow_completed (Socket.IO)", ha="center", fontsize=7.5, color=C_TEXT)

    # Líneas de vida
    for _, px, _ in participants:
        ax.plot([px, px], [0.5, 9.5], color="#CFD8DC", linewidth=1, linestyle="--", zorder=0)

    fig.tight_layout()
    path = OUT / "flujo_lead_workflow.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def diagrama_mapa_servicios():
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Mapa Servicio → Carpeta → Puerto", fontsize=16, fontweight="bold", pad=16, color=C_TEXT)

    services = [
        ("Puerto 8000 — Web", C_WEB, [
            "entrypoints/web_wsgi.py",
            "routes/auth · crm · marketing · agents",
            "templates/ + static/",
        ]),
        ("Celery Worker", C_WORKER, [
            "core/celery_app.py",
            "agents/lead_workflow/celery_tasks.py",
            "agents/lead_workflow/orchestrator.py",
        ]),
        ("Puerto 8001 — Agent Services", C_AGENTS, [
            "entrypoints/agent_service.py",
            "agents/lead_workflow/distributed/agent_server.py",
            "agents/lead_workflow/agents/*",
        ]),
        ("Compartido (todos los procesos)", C_INFRA, [
            "core/config.py · core/extensions.py",
            "models/ · db/",
        ]),
    ]

    x_positions = [0.5, 3.8, 7.1, 10.4]
    for (title, color, lines), x in zip(services, x_positions):
        text = "\n".join(f"• {l}" for l in lines)
        _box(ax, x, 1.5, 3.0, 4.5, text, color, fontsize=8.5, bold_title=title)

    _arrow(ax, 3.5, 3.8, 7.1, 3.8, "HTTP REST")
    _arrow(ax, 3.5, 3.2, 7.1, 3.2, "encola vía Redis")
    ax.text(7.0, 5.5, "Misma imagen Docker · distinto comando de arranque",
            ha="center", fontsize=10, style="italic", color=C_ARROW)

    fig.tight_layout()
    path = OUT / "mapa_servicios_carpetas.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def diagrama_estructura_carpetas():
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Estructura de Carpetas — CRM Orbes", fontsize=16, fontweight="bold", pad=16, color=C_TEXT)

    tree = """crm_flask/
├── core/              config · extensions · celery
├── entrypoints/       web (:8000) · agent-services (:8001)
├── routes/
│   ├── auth/          login · register · usuarios
│   ├── crm/           leads · dashboard · reportes
│   ├── marketing/     campañas · ferias · OKR
│   └── agents/        chat · IA · monitor · workflow
├── agents/
│   ├── broker/        orquestador chat multiagente
│   ├── core/          agentes in-process (ML, reportes)
│   └── lead_workflow/
│       ├── agents/    scoring · commercial · recovery · closing
│       ├── distributed/  HTTP client/server
│       └── orchestrator.py · celery_tasks.py
├── models/ · services/ · utils/
├── db/schemas/ · db/migrations/
├── infra/             docker-compose · gunicorn
├── docs/diagrams/     documentación visual
├── static/ · templates/
└── scripts/           mantenimiento y utilidades"""

    ax.text(0.5, 9.2, tree, ha="left", va="top", fontsize=10, family="monospace",
            color=C_TEXT, linespacing=1.45,
            bbox=dict(boxstyle="round,pad=0.6", facecolor="#FAFAFA", edgecolor=C_BORDER))

    fig.tight_layout()
    path = OUT / "estructura_carpetas.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


if __name__ == "__main__":
    paths = [
        diagrama_arquitectura_general(),
        diagrama_flujo_lead(),
        diagrama_mapa_servicios(),
        diagrama_estructura_carpetas(),
    ]
    for p in paths:
        print(f"Generado: {p}")

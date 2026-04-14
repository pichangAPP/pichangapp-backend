#!/usr/bin/env python3
"""Generate services/rasa/data/nlu_inform_generated.yml (>=1000 NLU example lines).

Must stay aligned with lookup location + sport synonyms in data/nlu.yml.
Re-run after changing districts or domain entities: python scripts/generate_inform_nlu.py
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# --- Canonical lists (mirror lookup: location / sport + surface synonym keys in nlu.yml) ---
DISTRICTS: tuple[str, ...] = (
    "Ancón",
    "Ate",
    "Barranco",
    "Breña",
    "Carabayllo",
    "Cieneguilla",
    "Comas",
    "Chaclacayo",
    "Chorrillos",
    "El Agustino",
    "Independencia",
    "Jesús María",
    "La Molina",
    "La Victoria",
    "Lima",
    "Lince",
    "Los Olivos",
    "Lurigancho",
    "Lurín",
    "Magdalena del Mar",
    "Miraflores",
    "Pachacámac",
    "Pucusana",
    "Pueblo Libre",
    "Puente Piedra",
    "Punta Hermosa",
    "Punta Negra",
    "Rímac",
    "San Bartolo",
    "San Borja",
    "San Isidro",
    "San Juan de Lurigancho",
    "San Juan de Miraflores",
    "San Luis",
    "San Martín de Porres",
    "San Miguel",
    "Santa Anita",
    "Santa María del Mar",
    "Santa Rosa",
    "Santiago de Surco",
    "Surquillo",
    "Villa El Salvador",
    "Villa María del Triunfo",
)

SPORTS: tuple[str, ...] = (
    "fútbol",
    "futbol",
    "basketball",
    "basquet",
    "vóley",
    "voley",
    "tenis",
    "pádel",
    "padel",
    "fulbito",
    "futsal",
)

# Sin "Grass mixto (natural + sintético)" en plantillas: el WhitespaceTokenizer parte en '(' y desalinea la entidad.
SURFACES: tuple[str, ...] = (
    "Grass sintético",
    "Grass natural",
    "Grass sintético premium",
    "Losa de cemento",
    "Losa deportiva",
)

# Patrón alineado con nlu.yml (entidad solo sobre "Grass mixto").
SURFACE_MIXTO_SAFE: tuple[str, ...] = (
    "dato [Grass mixto](surface) natural y sintético",
    "nomás [Grass mixto](surface) natural y sintético",
    "tipo [Grass mixto](surface) natural y sintético",
    "prefiero [Grass mixto](surface) natural y sintético",
    "sale [Grass mixto](surface) natural y sintético",
    "pa [Grass mixto](surface) natural y sintético",
    "full [Grass mixto](surface) natural y sintético",
    "me sirve [Grass mixto](surface) natural y sintético",
)

TIMES: tuple[str, ...] = (
    "07:00",
    "08:00",
    "08:30",
    "09:00",
    "10:00",
    "12:00",
    "15:00",
    "17:00",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
    "20:00",
    "20:30",
    "21:00",
    "21:30",
    "22:00",
    "8pm",
    "9pm",
    "7:30pm",
    "10pm",
)

DATES: tuple[str, ...] = (
    "hoy",
    "mañana",
    "pasado mañana",
    "este sábado",
    "el domingo",
    "el lunes",
)

BUDGETS: tuple[str, ...] = (
    "S/40",
    "S/50",
    "S/60",
    "S/70",
    "S/80",
    "S/90",
    "S/100",
    "S/120",
    "S/150",
    "S/200",
    "80 soles",
    "100 soles",
    "120 lucas",
)

PLAYERS: tuple[str, ...] = ("6", "8", "10", "12", "14", "16", "18", "22")

MIN_EXAMPLE_LINES = 1000


def _collect_inform_examples() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(line: str) -> None:
        line = line.strip()
        if not line or line in seen:
            return
        seen.add(line)
        out.append(line)

    # --- location (plantillas peruanas / coloquiales) ---
    # Frases orientadas a respuesta de formulario; evitar duplicar textos de request_field_recommendation en nlu.yml.
    loc_tmpl = (
        "jugamos en [{d}](location)",
        "distrito [{d}](location)",
        "prefiero [{d}](location)",
        "salimos de [{d}](location)",
        "somos de [{d}](location)",
        "pa la [{d}](location)",
        "full [{d}](location)",
        "pa jugar en [{d}](location)",
        "de [{d}](location) nomás",
        "nomás [{d}](location)",
        "dato distrito [{d}](location)",
        "elijo [{d}](location)",
        "to [{d}](location)",
        "queda en [{d}](location)",
        "sale [{d}](location)",
        "me sirve [{d}](location)",
        "vivimos cerca [{d}](location)",
        "estamos por [{d}](location)",
        "pal partido en [{d}](location)",
        "junto al distrito [{d}](location)",
        "barrio hacia [{d}](location)",
        "caigo a [{d}](location)",
        "me muevo a [{d}](location)",
        "rumbo a [{d}](location)",
    )
    for d in DISTRICTS:
        for t in loc_tmpl:
            add(t.format(d=d))

    # --- time ---
    time_tmpl = (
        "a las [{t}](time)",
        "tipo [{t}](time)",
        "como a las [{t}](time)",
        "a la [{t}](time)",
        "horario [{t}](time)",
        "entre [{t}](time) y listo",
        "después de las [{t}](time)",
        "antes de las [{t}](time)",
        "más o menos [{t}](time)",
        "tipo noche [{t}](time)",
        "pa las [{t}](time)",
        "full [{t}](time)",
    )
    for t in TIMES:
        for tmpl in time_tmpl:
            add(tmpl.format(t=t))

    # --- date ---
    date_tmpl = (
        "[{dt}](date)",
        "sería [{dt}](date)",
        "el día [{dt}](date)",
        "tipo [{dt}](date)",
        "pa el [{dt}](date)",
        "me sirve [{dt}](date)",
        "nomás [{dt}](date)",
        "sale [{dt}](date)",
    )
    for dt in DATES:
        for tmpl in date_tmpl:
            add(tmpl.format(dt=dt))

    # --- budget ---
    bud_tmpl = (
        "presupuesto [{b}](budget)",
        "entre [{b}](budget) y barato",
        "tipo [{b}](budget)",
        "pa [{b}](budget)",
        "full [{b}](budget)",
        "nomás [{b}](budget)",
        "me alcanza [{b}](budget)",
        "con [{b}](budget) nomás",
        "dato plata [{b}](budget)",
        "sale [{b}](budget)",
    )
    for b in BUDGETS:
        for tmpl in bud_tmpl:
            add(tmpl.format(b=b))

    # --- sport ---
    sport_tmpl = (
        "[{s}](sport)",
        "nomás [{s}](sport)",
        "juego [{s}](sport)",
        "pa [{s}](sport)",
        "full [{s}](sport)",
        "tipo [{s}](sport)",
        "pelota [{s}](sport)",
        "pichanga [{s}](sport)",
        "mi deporte [{s}](sport)",
        "sale [{s}](sport)",
    )
    for s in SPORTS:
        for tmpl in sport_tmpl:
            add(tmpl.format(s=s))

    # --- surface ---
    surf_tmpl = (
        "[{sf}](surface)",
        "superficie [{sf}](surface)",
        "nomás [{sf}](surface)",
        "tipo [{sf}](surface)",
        "full [{sf}](surface)",
        "pa [{sf}](surface)",
        "dato piso [{sf}](surface)",
        "sale [{sf}](surface)",
        "me sirve [{sf}](surface)",
    )
    for sf in SURFACES:
        for tmpl in surf_tmpl:
            add(tmpl.format(sf=sf))
    for line in SURFACE_MIXTO_SAFE:
        add(line)

    # --- num_players ---
    np_tmpl = (
        "somos [{n}](num_players)",
        "somos [{n}](num_players) jugadores",
        "[{n}](num_players) jugadores",
        "jugamos [{n}](num_players)",
        "tipo [{n}](num_players) nomás",
        "full [{n}](num_players)",
        "pa [{n}](num_players) contra [{n2}](num_players)",
    )
    for n in PLAYERS:
        for tmpl in np_tmpl:
            if "{n2}" in tmpl:
                for n2 in PLAYERS:
                    if n != n2:
                        add(tmpl.format(n=n, n2=n2))
            else:
                add(tmpl.format(n=n))

    # --- multi-entidad (mezclas acotadas; no inflar demasiado) ---
    for d in DISTRICTS[:25]:
        add(f"en [{d}](location) a las [20:00](time)")
        add(f"en [{d}](location) [fútbol](sport)")
        add(f"en [{d}](location) [Grass sintético](surface)")
        add(f"en [{d}](location) hasta [S/100](budget)")
        add(f"en [{d}](location) [mañana](date)")
        add(f"[fútbol](sport) en [{d}](location) a las [19:00](time)")
        add(f"hasta [S/80](budget) en [{d}](location)")
        add(f"[Losa deportiva](surface) en [{d}](location)")
        add(f"somos [10](num_players) en [{d}](location)")

    for d in DISTRICTS[25:]:
        add(f"por [{d}](location) [basquet](sport)")
        add(f"zona [{d}](location) [8pm](time)")

    # deterministic extra fillers if still short (combinaciones únicas)
    idx = 0
    while len(out) < MIN_EXAMPLE_LINES:
        d = DISTRICTS[idx % len(DISTRICTS)]
        t = TIMES[(idx // 2) % len(TIMES)]
        s = SPORTS[idx % len(SPORTS)]
        b = BUDGETS[idx % len(BUDGETS)]
        add(f"en [{d}](location) [{s}](sport) a las [{t}](time) hasta [{b}](budget)")
        idx += 1

    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_path = root / "data" / "nlu_inform_generated.yml"

    inform_lines = _collect_inform_examples()

    digest = hashlib.sha256("\n".join(inform_lines).encode("utf-8")).hexdigest()[:12]

    body_inform = "\n".join(f"      - {x}" for x in inform_lines)

    content = f"""version: "3.1"

# Auto-generated by scripts/generate_inform_nlu.py (sha256-prefix {digest})
# Do not edit by hand; re-run:  python scripts/generate_inform_nlu.py
# Inform examples: {len(inform_lines)}

nlu:
  - intent: inform
    examples: |
{body_inform}
"""
    out_path.write_text(content, encoding="utf-8")
    total_yaml_lines = len(content.splitlines())
    print(f"Wrote {out_path}")
    print(f"  inform examples: {len(inform_lines)} (min required {MIN_EXAMPLE_LINES})")
    print(f"  total YAML lines: {total_yaml_lines}")


if __name__ == "__main__":
    main()

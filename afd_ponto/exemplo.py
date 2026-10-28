"""Gera um AFD fictício (layout 1510) para testar e demonstrar sem dados reais."""
import random
from datetime import date, datetime, timedelta

EMPRESA = "INDUSTRIA EXEMPLO LTDA"
CNPJ = "11222333000181"


def pis_ficticio(rng):
    """PIS com dígito verificador válido (gerado aleatoriamente, não pertence a ninguém)."""
    base = [rng.randint(0, 9) for _ in range(10)]
    base[0] = rng.randint(1, 9)
    soma = sum(d * p for d, p in zip(base, (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)))
    dv = 11 - soma % 11
    return "".join(map(str, base)) + str(0 if dv >= 10 else dv)


# (nome, turno) — turno = horários-base de entrada, saída almoço, volta, saída
EQUIPE = [
    ("ANA PEREIRA", ("07:00", "11:00", "12:00", "16:00")),
    ("BRUNO COSTA", ("07:00", "11:30", "12:00", "16:00")),   # almoço curto de propósito
    ("CARLA SOUZA", ("14:00", "18:00", "19:00", "23:00")),
    ("DIEGO LIMA", ("22:00", "02:00", "03:00", "06:00")),    # turno da noite, vira o dia
]


def gerar(inicio=date(2026, 10, 1), dias=10, semente=7):
    rng = random.Random(semente)
    linhas = []
    nsr = 0

    def registro(tipo, corpo):
        nonlocal nsr
        nsr += 1
        linhas.append(f"{nsr:09d}{tipo}{corpo}")

    fim = inicio + timedelta(days=dias - 1)
    agora = datetime.combine(fim, datetime.min.time()) + timedelta(days=1, hours=8)
    linhas.append(
        "000000000" + "1" + "1" + CNPJ + " " * 12 + f"{EMPRESA:<150}" + f"{'00004000000000001':<17}"
        + inicio.strftime("%d%m%Y") + fim.strftime("%d%m%Y") + agora.strftime("%d%m%Y%H%M"))

    equipe = [(nome, turno, pis_ficticio(rng)) for nome, turno in EQUIPE]
    for nome, _, pis in equipe:
        registro("5", inicio.strftime("%d%m%Y") + "0600" + "I" + pis.zfill(12) + f"{nome:<52}")

    marcacoes = []
    for d in range(dias):
        dia = inicio + timedelta(days=d)
        if dia.weekday() == 6:  # domingo de folga
            continue
        for nome, turno, pis in equipe:
            base = datetime.combine(dia, datetime.min.time())
            anterior = None
            for k, hhmm in enumerate(turno):
                h, m = map(int, hhmm.split(":"))
                momento = base + timedelta(hours=h, minutes=m + rng.randint(-6, 6))
                if anterior and momento < anterior:  # passou da meia-noite
                    momento += timedelta(days=1)
                    base += timedelta(days=1)
                anterior = momento
                if nome == "ANA PEREIRA" and d == 1 and k == 3:
                    continue  # esqueceu de bater a saída
                marcacoes.append((momento, pis))
            if nome == "ANA PEREIRA" and d == 4:
                marcacoes.append((base + timedelta(hours=18, minutes=30), pis))  # hora extra
                marcacoes.append((base + timedelta(hours=16, minutes=15), pis))

    for momento, pis in sorted(marcacoes):
        registro("3", momento.strftime("%d%m%Y%H%M") + pis.zfill(12))
    linhas.append(f"{999999999:09d}" + f"{0:09d}{len(marcacoes):09d}{0:09d}{len(equipe):09d}" + "9")
    return "\r\n".join(linhas) + "\r\n"

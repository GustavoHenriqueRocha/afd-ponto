"""Monta as jornadas a partir das marcações e confere as regras básicas da CLT.

Uma jornada é uma sequência de batidas com menos de `separacao` horas entre
uma e outra. Enquanto a jornada está aberta (número ímpar de batidas), a
próxima batida em até `turno_maximo` horas ainda é a saída: assim um turno de
12 h sem batida de almoço não vira duas jornadas, e um turno que vira a
meia-noite (22:00 → 06:00) fica no dia em que começou.

O que é conferido (apenas como alerta; quem decide é o RH):
- batida ímpar (faltou registrar entrada ou saída);
- intervalo intrajornada menor que 1 h em jornada acima de 6 h (CLT art. 71),
  com `tolerancia_intervalo` de folga para não acusar um almoço de 58 min;
- intervalo interjornada menor que 11 h (CLT art. 66);
- horas além da jornada contratada, desprezando variações de até 10 min por
  dia (CLT art. 58, § 1º);
- horas noturnas (22:00–05:00) com a hora reduzida de 52 min 30 s (CLT art. 73).
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

NOTURNO_INICIO = 22
NOTURNO_FIM = 5


@dataclass
class Jornada:
    pis: str
    dia: date
    batidas: list[datetime]
    trabalhado: timedelta = timedelta()
    noturno: timedelta = timedelta()          # relógio, sem a redução
    extra: timedelta = timedelta()
    alertas: list[str] = field(default_factory=list)

    @property
    def noturno_reduzido(self):
        """Horas noturnas como a CLT conta: cada 52 min 30 s vale 1 h."""
        return self.noturno * 60 / 52.5


def minutos_noturnos(inicio, fim):
    """Quanto do intervalo [inicio, fim) cai entre 22:00 e 05:00."""
    total = timedelta()
    dia = inicio.date() - timedelta(days=1)
    while datetime.combine(dia, datetime.min.time()) < fim:
        janela_ini = datetime.combine(dia, datetime.min.time()) + timedelta(hours=NOTURNO_INICIO)
        janela_fim = datetime.combine(dia + timedelta(days=1), datetime.min.time()) + timedelta(hours=NOTURNO_FIM)
        sobreposto = min(fim, janela_fim) - max(inicio, janela_ini)
        if sobreposto > timedelta():
            total += sobreposto
        dia += timedelta(days=1)
    return total


def montar(marcacoes, jornada_diaria=timedelta(hours=8), separacao=timedelta(hours=6),
           turno_maximo=timedelta(hours=16), tolerancia_extra=timedelta(minutes=10),
           tolerancia_intervalo=timedelta(minutes=5)):
    """Devolve {pis: [Jornada, ...]} em ordem cronológica."""
    por_pis = {}
    for m in marcacoes:
        por_pis.setdefault(m.pis, set()).add(m.momento)  # batida repetida no mesmo minuto conta uma vez

    resultado = {}
    for pis, momentos in por_pis.items():
        grupos = []
        for momento in sorted(momentos):
            if grupos:
                vao = momento - grupos[-1][-1]
                aberta = len(grupos[-1]) % 2 == 1
            if grupos and (vao < separacao or (aberta and vao <= turno_maximo)):
                grupos[-1].append(momento)
            else:
                grupos.append([momento])

        jornadas = []
        for batidas in grupos:
            j = Jornada(pis, batidas[0].date(), batidas)
            maior_intervalo = timedelta()
            for i in range(0, len(batidas) - 1, 2):
                entrada, saida = batidas[i], batidas[i + 1]
                j.trabalhado += saida - entrada
                j.noturno += minutos_noturnos(entrada, saida)
                if i + 2 < len(batidas):
                    maior_intervalo = max(maior_intervalo, batidas[i + 2] - saida)
            if len(batidas) % 2:
                j.alertas.append("batida ímpar")
            if (j.trabalhado > timedelta(hours=6) and len(batidas) >= 4
                    and maior_intervalo < timedelta(hours=1) - tolerancia_intervalo):
                j.alertas.append(f"intervalo de almoço de {formatar(maior_intervalo)} (mínimo 1 h)")
            elif j.trabalhado > timedelta(hours=6) and len(batidas) == 2:
                j.alertas.append("jornada acima de 6 h sem intervalo registrado")
            if j.trabalhado - jornada_diaria > tolerancia_extra:
                j.extra = j.trabalhado - jornada_diaria
            if jornadas:
                descanso = batidas[0] - jornadas[-1].batidas[-1]
                if descanso < timedelta(hours=11):
                    j.alertas.append(f"descanso entre jornadas de {formatar(descanso)} (mínimo 11 h)")
            jornadas.append(j)
        resultado[pis] = jornadas
    return resultado


def formatar(duracao):
    minutos = round(duracao.total_seconds() / 60)
    return f"{minutos // 60}h{minutos % 60:02d}"

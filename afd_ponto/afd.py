"""Leitura do AFD (Arquivo-Fonte de Dados) dos relógios de ponto REP.

Entende o layout da Portaria 1510/2009 e o registro de marcação (tipo 3) da
Portaria 671/2021. Cada linha começa com o NSR (9 dígitos) e o tipo (1 dígito):

    1 cabeçalho   2 empresa   3 marcação   4 ajuste de relógio
    5 funcionário 6 evento    9 trailer

Linhas de tipos desconhecidos são ignoradas sem erro: cada fabricante
acrescenta alguma coisa (o tipo 5 de alguns Topdata vem com o CPF do
responsável no final, por exemplo).
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Marcacao:
    nsr: int
    momento: datetime
    pis: str  # PIS (1510) ou CPF (671), 12 dígitos


@dataclass(frozen=True)
class Funcionario:
    nsr: int
    momento: datetime
    operacao: str  # I inclusão, A alteração, E exclusão
    pis: str
    nome: str


@dataclass
class Afd:
    cnpj: str = ""
    razao_social: str = ""
    numero_rep: str = ""
    marcacoes: list[Marcacao] = field(default_factory=list)
    funcionarios: list[Funcionario] = field(default_factory=list)
    ajustes_relogio: int = 0
    linhas_invalidas: list[tuple[int, str]] = field(default_factory=list)
    nsrs: list[int] = field(default_factory=list)

    def nomes(self):
        """PIS → nome, pela última inclusão/alteração registrada no próprio AFD."""
        nomes = {}
        for f in sorted(self.funcionarios, key=lambda f: f.nsr):
            if f.operacao == "E":
                nomes.pop(f.pis, None)
            else:
                nomes[f.pis] = f.nome
        return nomes

    def buracos_nsr(self):
        """Faixas de NSR que faltam. Buraco no NSR = registro perdido ou arquivo editado."""
        faltando = []
        seq = sorted(set(self.nsrs))
        for anterior, atual in zip(seq, seq[1:]):
            if atual - anterior > 1:
                faltando.append((anterior + 1, atual - 1))
        return faltando


def _data_hora(ddmmaaaa, hhmm):
    return datetime.strptime(ddmmaaaa + hhmm, "%d%m%Y%H%M")


def ler_texto(texto):
    afd = Afd()
    for numero, linha in enumerate(texto.splitlines(), 1):
        linha = linha.rstrip("\r\n")
        if not linha.strip():
            continue
        if len(linha) < 10 or not linha[:9].isdigit():
            afd.linhas_invalidas.append((numero, "linha sem NSR"))
            continue
        if linha.startswith("999999999"):
            continue  # trailer (1510): o tipo "9" fica no fim da linha, não na posição 10
        nsr, tipo = int(linha[:9]), linha[9]
        try:
            if tipo == "1":
                afd.cnpj = linha[11:25].strip()
                afd.razao_social = linha[37:187].strip()
                afd.numero_rep = linha[187:204].strip()
                continue  # o cabeçalho usa NSR 0 e fica fora da sequência
            if tipo == "3":
                if len(linha) >= 50 and linha[14] == "-":  # Portaria 671: data/hora ISO 8601
                    momento = datetime.fromisoformat(linha[10:34]).replace(tzinfo=None)
                    afd.marcacoes.append(Marcacao(nsr, momento, linha[34:46]))
                else:
                    afd.marcacoes.append(Marcacao(nsr, _data_hora(linha[10:18], linha[18:22]), linha[22:34]))
            elif tipo == "5":
                afd.funcionarios.append(Funcionario(
                    nsr, _data_hora(linha[10:18], linha[18:22]), linha[22],
                    linha[23:35], linha[35:87].strip()))
            elif tipo == "4":
                afd.ajustes_relogio += 1
            elif tipo == "9":
                continue  # o trailer não entra na sequência de NSR
        except (ValueError, IndexError) as e:
            afd.linhas_invalidas.append((numero, f"tipo {tipo}: {e}"))
            continue
        afd.nsrs.append(nsr)
    return afd


def ler(caminho):
    # REPs gravam em ISO-8859-1; latin-1 nunca falha, então o UTF-8 vem primeiro.
    dados = Path(caminho).read_bytes()
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        texto = dados.decode("latin-1")
    return ler_texto(texto)


def pis_valido(pis):
    """Confere o dígito verificador do PIS/PASEP/NIT (11 dígitos significativos)."""
    digitos = pis.strip().lstrip("0").zfill(11)
    if len(digitos) != 11 or not digitos.isdigit():
        return False
    soma = sum(int(d) * p for d, p in zip(digitos[:10], (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)))
    dv = 11 - soma % 11
    return int(digitos[10]) == (0 if dv >= 10 else dv)

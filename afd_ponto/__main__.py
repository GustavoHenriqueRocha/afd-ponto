"""Linha de comando: espelho de ponto, conferência do arquivo e AFD de exemplo."""
import argparse
import csv
import json
import sys
from datetime import date, timedelta

from . import __version__
from .afd import ler, pis_valido
from .exemplo import gerar
from .jornada import formatar, montar


def _nomes_csv(caminho):
    """CSV `pis;nome` opcional, para quando o AFD não traz os registros tipo 5."""
    nomes = {}
    with open(caminho, encoding="utf-8-sig") as f:
        for linha in csv.reader(f, delimiter=";"):
            if len(linha) >= 2 and linha[0].strip().isdigit():
                nomes[linha[0].strip().zfill(12)] = linha[1].strip()
    return nomes


def _filtrar(jornadas, de, ate):
    return {pis: [j for j in js if (not de or j.dia >= de) and (not ate or j.dia <= ate)]
            for pis, js in jornadas.items()}


def cmd_espelho(a):
    afd = ler(a.arquivo)
    nomes = afd.nomes()
    if a.nomes:
        nomes.update(_nomes_csv(a.nomes))
    jornadas = _filtrar(montar(afd.marcacoes, timedelta(hours=a.jornada)), a.de, a.ate)

    linhas = []
    for pis in sorted(jornadas, key=lambda p: nomes.get(p, p)):
        for j in jornadas[pis]:
            linhas.append({
                "pis": pis, "nome": nomes.get(pis, ""), "dia": j.dia.isoformat(),
                "batidas": " ".join(b.strftime("%H:%M") for b in j.batidas),
                "trabalhado": formatar(j.trabalhado), "extra": formatar(j.extra),
                "noturno": formatar(j.noturno_reduzido), "alertas": "; ".join(j.alertas),
            })

    if a.json:
        json.dump(linhas, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:  # BOM: o Excel abre com acento certo
            w = csv.DictWriter(f, fieldnames=list(linhas[0]) if linhas else ["pis"], delimiter=";")
            w.writeheader()
            w.writerows(linhas)
        print(f"{len(linhas)} jornadas gravadas em {a.csv}")
    else:
        atual = None
        for l in linhas:
            if l["pis"] != atual:
                atual = l["pis"]
                print(f"\n{l['nome'] or 'sem nome'} — PIS {l['pis']}")
            extra = f"  +{l['extra']} extra" if l["extra"] != "0h00" else ""
            noturno = f"  {l['noturno']} noturno" if l["noturno"] != "0h00" else ""
            alerta = f"  ⚠ {l['alertas']}" if l["alertas"] else ""
            print(f"  {l['dia']}  {l['batidas']:<24} {l['trabalhado']:>6}{extra}{noturno}{alerta}")
    return 0


def cmd_conferir(a):
    afd = ler(a.arquivo)
    problemas = 0
    print(f"empresa: {afd.razao_social or '?'} (CNPJ {afd.cnpj or '?'}), REP {afd.numero_rep or '?'}")
    print(f"marcações: {len(afd.marcacoes)} | funcionários cadastrados: {len(afd.nomes())}"
          f" | ajustes de relógio: {afd.ajustes_relogio}")
    for ini, fim in afd.buracos_nsr():
        problemas += 1
        print(f"  ⚠ faltam os NSR {ini}" + (f" a {fim}" if fim != ini else ""))
    for pis in sorted({m.pis for m in afd.marcacoes}):
        if not pis_valido(pis):
            problemas += 1
            print(f"  ⚠ PIS com dígito verificador inválido: {pis}")
    for numero, motivo in afd.linhas_invalidas:
        problemas += 1
        print(f"  ⚠ linha {numero}: {motivo}")
    print("nenhum problema encontrado" if not problemas else f"{problemas} problema(s)")
    return 1 if problemas else 0


def cmd_exemplo(_):
    sys.stdout.write(gerar())
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="afd-ponto", description="Espelho de ponto a partir do AFD de relógios REP.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="comando", required=True)

    sp = sub.add_parser("espelho", help="monta as jornadas por funcionário")
    sp.add_argument("arquivo")
    sp.add_argument("--nomes", help="CSV pis;nome (opcional; o AFD já traz os nomes no tipo 5)")
    sp.add_argument("--jornada", type=float, default=8, help="horas contratadas por dia (padrão 8)")
    sp.add_argument("--de", type=date.fromisoformat, help="primeiro dia, AAAA-MM-DD")
    sp.add_argument("--ate", type=date.fromisoformat, help="último dia, AAAA-MM-DD")
    saida = sp.add_mutually_exclusive_group()
    saida.add_argument("--csv", help="grava em CSV (abre direto no Excel)")
    saida.add_argument("--json", action="store_true", help="imprime em JSON")
    sp.set_defaults(func=cmd_espelho)

    sp = sub.add_parser("conferir", help="procura NSR faltando, PIS inválido e linhas quebradas")
    sp.add_argument("arquivo")
    sp.set_defaults(func=cmd_conferir)

    sp = sub.add_parser("exemplo", help="imprime um AFD fictício para testar")
    sp.set_defaults(func=cmd_exemplo)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())

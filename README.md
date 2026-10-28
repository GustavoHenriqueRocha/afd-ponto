# afd-ponto

![testes](https://github.com/GustavoHenriqueRocha/afd-ponto/actions/workflows/testes.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![dependências](https://img.shields.io/badge/depend%C3%AAncias-nenhuma-39d98a)

Transforma o **AFD** (Arquivo-Fonte de Dados) de relógios de ponto **REP** em espelho de ponto por funcionário: horas trabalhadas, hora extra, adicional noturno e alertas das regras básicas da CLT.
Lê o layout da **Portaria 1510/2009** e o registro de marcação da **Portaria 671/2021**. Python puro, sem dependências.

```text
$ afd-ponto espelho afd.txt

ANA PEREIRA — PIS 092601815906
  2026-10-01  06:55 11:03 12:03 16:04    8h09
  2026-10-02  07:02 11:00 12:06          3h58  ⚠ batida ímpar
  2026-10-05  06:56 11:01 12:00 15:54 16:15 18:30  10h14  +2h14 extra

CARLA SOUZA — PIS 011390996039
  2026-10-05  14:03 18:06 18:59 22:59    8h03  1h07 noturno  ⚠ intervalo de almoço de 0h53 (mínimo 1 h)

DIEGO LIMA — PIS 032462819483
  2026-10-01  22:03 01:57 03:01 06:04    6h57  6h43 noturno
```

*(dados fictícios, gerados por `afd-ponto exemplo`)*

## O que ele resolve

O AFD é um arquivo de texto de largura fixa. Somar as batidas parece simples até aparecerem os casos reais:

- **Turno que vira a meia-noite.** 22:00 → 06:00 é uma jornada só, contada no dia em que começou, e não duas metades em dias diferentes.
- **Turno longo sem batida de almoço.** 07:58 → 18:08 não vira duas jornadas de uma batida. Enquanto a jornada está aberta (batidas em número ímpar), a próxima batida em até 16 h ainda é a saída.
- **Batida esquecida ou repetida.** Uma batida ímpar vira alerta, e a mesma batida registrada duas vezes no mesmo minuto conta uma vez.
- **Arquivo adulterado ou incompleto.** O comando `conferir` acusa buracos na sequência de NSR, PIS com dígito verificador inválido e linhas quebradas.
- **Variações de cada fabricante.** Campos extras no fim do registro (como o CPF do responsável que alguns modelos acrescentam no tipo 5) são tolerados. O arquivo é lido em UTF-8 ou ISO-8859-1.

## Regras conferidas

São apenas alertas: a decisão final é do RH e do contrato de cada empresa.

| Regra | Base |
|---|---|
| Intervalo de almoço de no mínimo 1 h em jornada acima de 6 h (tolerância de 5 min) | CLT art. 71 |
| Descanso de no mínimo 11 h entre jornadas | CLT art. 66 |
| Hora extra acima da jornada contratada, desprezando variações de até 10 min por dia | CLT art. 58, § 1º |
| Horas entre 22:00 e 05:00 contadas com a hora noturna reduzida (52 min 30 s) | CLT art. 73 |

A jornada contratada muda com `--jornada 6`, por exemplo, e os limites são parâmetros de `montar()`.

## Uso

```bash
afd-ponto exemplo > afd.txt                        # AFD fictício para testar
afd-ponto conferir afd.txt                         # NSR faltando, PIS inválido, linhas quebradas
afd-ponto espelho afd.txt                          # espelho na tela
afd-ponto espelho afd.txt --de 2026-10-01 --ate 2026-10-15 --csv espelho.csv   # abre direto no Excel
afd-ponto espelho afd.txt --json                   # para integrar com outro sistema
afd-ponto espelho afd.txt --nomes nomes.csv        # CSV pis;nome, se o AFD não trouxer os nomes
```

Instale com `pip install .` ou rode sem instalar com `python -m afd_ponto`.

Os nomes vêm do próprio AFD (registros tipo 5, respeitando inclusão, alteração e exclusão). O CSV de `--nomes` só é necessário quando o arquivo exportado não traz esses registros.

### Como biblioteca

```python
from afd_ponto.afd import ler
from afd_ponto.jornada import montar

afd = ler("afd.txt")
for pis, jornadas in montar(afd.marcacoes).items():
    for j in jornadas:
        print(afd.nomes().get(pis), j.dia, j.trabalhado, j.extra, j.noturno_reduzido, j.alertas)
```

## Testes

```bash
python -m unittest discover -s tests -v
```

Cobrem os dois layouts, campos extras de fabricante, exclusão de funcionário, buraco de NSR, arquivo em latin-1, turno da noite, turno de 12 h sem almoço, tolerâncias da CLT e a linha de comando de ponta a ponta. O parser também foi validado com o AFD real de um relógio Topdata Inner Rep (411 marcações), que não está no repositório.

## Limitações

- O CRC-16 dos registros da Portaria 671 não é conferido.
- Feriados, DSR, banco de horas e escalas especiais (12×36) não são tratados: o espelho mostra as horas, e o enquadramento fica com o RH.

## Licença

MIT

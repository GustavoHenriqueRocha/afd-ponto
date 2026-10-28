import io
import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path

from afd_ponto.__main__ import main
from afd_ponto.afd import Marcacao, ler, ler_texto, pis_valido
from afd_ponto.exemplo import gerar, pis_ficticio
from afd_ponto.jornada import formatar, minutos_noturnos, montar

PIS = "012345678901"


def m(texto, pis=PIS, nsr=1):
    return Marcacao(nsr, datetime.strptime(texto, "%d/%m %H:%M").replace(year=2026), pis)


def jornadas(*batidas, **kw):
    return montar([m(b) for b in batidas], **kw)[PIS]


class TestLeitura(unittest.TestCase):
    def test_layout_1510(self):
        afd = ler_texto("0000000013" + "011020260758" + PIS + "\r\n")
        self.assertEqual(afd.marcacoes, [Marcacao(1, datetime(2026, 10, 1, 7, 58), PIS)])

    def test_layout_671(self):
        afd = ler_texto("0000000023" + "2026-10-01T07:58:00-0300" + PIS + "ABCD")
        self.assertEqual(afd.marcacoes[0].momento, datetime(2026, 10, 1, 7, 58))
        self.assertEqual(afd.marcacoes[0].pis, PIS)

    def test_funcionario_com_campos_a_mais_do_fabricante(self):
        linha = "0000000055" + "010120260600" + "I" + PIS + f"{'FULANO DE TAL':<52}" + "    12345678901"
        self.assertEqual(ler_texto(linha).nomes(), {PIS: "FULANO DE TAL"})

    def test_exclusao_tira_o_nome(self):
        inc = "0000000015" + "010120260600" + "I" + PIS + f"{'FULANO':<52}"
        exc = "0000000025" + "020120260600" + "E" + PIS + f"{'FULANO':<52}"
        self.assertEqual(ler_texto(inc + "\n" + exc).nomes(), {})

    def test_buraco_no_nsr(self):
        linhas = [f"{n:09d}3011020260758{PIS}" for n in (1, 2, 5, 6)]
        self.assertEqual(ler_texto("\n".join(linhas)).buracos_nsr(), [(3, 4)])

    def test_trailer_e_cabecalho_nao_entram_na_sequencia(self):
        afd = ler_texto(gerar())
        self.assertEqual(afd.buracos_nsr(), [])
        self.assertEqual(afd.razao_social, "INDUSTRIA EXEMPLO LTDA")

    def test_linha_quebrada_vira_aviso_e_nao_erro(self):
        afd = ler_texto("0000000013" + "99999999" + "0758" + PIS)
        self.assertEqual(len(afd.linhas_invalidas), 1)
        self.assertEqual(afd.marcacoes, [])

    def test_arquivo_em_latin1(self):
        linha = "0000000015" + "010120260600" + "I" + PIS + f"{'JOÃO ÁVILA':<52}"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(linha.encode("latin-1"))
        try:
            self.assertEqual(ler(f.name).nomes()[PIS], "JOÃO ÁVILA")
        finally:
            Path(f.name).unlink()

    def test_pis_valido(self):
        rng = random.Random(1)
        for _ in range(50):
            pis = pis_ficticio(rng)
            self.assertTrue(pis_valido(pis.zfill(12)))
            errado = pis[:-1] + str((int(pis[-1]) + 1) % 10)
            self.assertFalse(pis_valido(errado))


class TestJornada(unittest.TestCase):
    def test_jornada_normal(self):
        (j,) = jornadas("01/10 07:00", "01/10 11:00", "01/10 12:00", "01/10 16:00")
        self.assertEqual((formatar(j.trabalhado), j.alertas), ("8h00", []))

    def test_turno_de_12h_sem_almoco_e_uma_jornada_so(self):
        (j,) = jornadas("01/10 07:58", "01/10 18:08")
        self.assertEqual(formatar(j.trabalhado), "10h10")
        self.assertIn("jornada acima de 6 h sem intervalo registrado", j.alertas)

    def test_turno_da_noite_fica_no_dia_em_que_comecou(self):
        (j,) = jornadas("01/10 22:00", "02/10 02:00", "02/10 03:00", "02/10 06:00")
        self.assertEqual(j.dia, date(2026, 10, 1))
        self.assertEqual(formatar(j.noturno), "6h00")          # 22–02 e 03–05
        self.assertEqual(formatar(j.noturno_reduzido), "6h51")  # 360 min × 60 / 52,5

    def test_batida_impar(self):
        (j,) = jornadas("01/10 07:00", "01/10 11:00", "01/10 12:00")
        self.assertIn("batida ímpar", j.alertas)

    def test_batida_repetida_no_mesmo_minuto_conta_uma_vez(self):
        (j,) = jornadas("01/10 07:00", "01/10 07:00", "01/10 16:00")
        self.assertEqual(len(j.batidas), 2)

    def test_almoco_curto(self):
        (j,) = jornadas("01/10 07:00", "01/10 11:30", "01/10 12:00", "01/10 16:00")
        self.assertIn("intervalo de almoço de 0h30 (mínimo 1 h)", j.alertas)

    def test_almoco_de_58_min_esta_na_tolerancia(self):
        (j,) = jornadas("01/10 07:00", "01/10 11:00", "01/10 11:58", "01/10 16:00")
        self.assertEqual(j.alertas, [])

    def test_extra_despreza_ate_10_min(self):
        (a,) = jornadas("01/10 07:00", "01/10 11:00", "01/10 12:00", "01/10 16:08")
        (b,) = jornadas("01/10 07:00", "01/10 11:00", "01/10 12:00", "01/10 16:30")
        self.assertEqual((a.extra, formatar(b.extra)), (timedelta(), "0h30"))

    def test_descanso_entre_jornadas(self):
        js = jornadas("01/10 14:00", "01/10 23:00", "02/10 07:00", "02/10 16:00")
        self.assertEqual(len(js), 2)
        self.assertIn("descanso entre jornadas de 8h00 (mínimo 11 h)", js[1].alertas)

    def test_jornada_contratada_configuravel(self):
        (j,) = jornadas("01/10 08:00", "01/10 12:00", "01/10 13:00", "01/10 17:00",
                        jornada_diaria=timedelta(hours=6))
        self.assertEqual(formatar(j.extra), "2h00")

    def test_noturno_fora_da_janela_e_zero(self):
        self.assertEqual(minutos_noturnos(datetime(2026, 10, 1, 8), datetime(2026, 10, 1, 17)), timedelta())


class TestLinhaDeComando(unittest.TestCase):
    def setUp(self):
        self.arquivo = Path(tempfile.mkdtemp()) / "afd.txt"
        self.arquivo.write_text(gerar(), encoding="latin-1")

    def rodar(self, *args):
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = main(list(args))
        return codigo, saida.getvalue()

    def test_espelho_do_exemplo(self):
        codigo, saida = self.rodar("espelho", str(self.arquivo))
        self.assertEqual(codigo, 0)
        self.assertIn("ANA PEREIRA", saida)
        self.assertIn("batida ímpar", saida)
        self.assertIn("+2h", saida)  # a hora extra plantada no exemplo

    def test_json_e_filtro_de_datas(self):
        _, saida = self.rodar("espelho", str(self.arquivo), "--json", "--de", "2026-10-05", "--ate", "2026-10-05")
        dias = {j["dia"] for j in json.loads(saida)}
        self.assertEqual(dias, {"2026-10-05"})

    def test_csv(self):
        csv = self.arquivo.with_suffix(".csv")
        self.rodar("espelho", str(self.arquivo), "--csv", str(csv))
        self.assertTrue(csv.read_text(encoding="utf-8-sig").startswith("pis;nome;dia"))

    def test_conferir_exemplo_sem_problemas(self):
        codigo, saida = self.rodar("conferir", str(self.arquivo))
        self.assertEqual(codigo, 0)
        self.assertIn("nenhum problema", saida)

    def test_conferir_acusa_nsr_faltando(self):
        linhas = self.arquivo.read_text(encoding="latin-1").splitlines()
        del linhas[10]
        self.arquivo.write_text("\n".join(linhas), encoding="latin-1")
        codigo, saida = self.rodar("conferir", str(self.arquivo))
        self.assertEqual(codigo, 1)
        self.assertIn("faltam os NSR", saida)


if __name__ == "__main__":
    unittest.main()

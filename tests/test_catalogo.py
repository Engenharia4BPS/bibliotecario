import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import organizar_biblioteca_pdf as app


class CatalogoTests(unittest.TestCase):
    def test_nao_confunde_cad_com_cada(self):
        self.assertEqual(app.keyword_matches("cada personagem", "cad"), 0)

    def test_categoria_publica_prioriza_fantasia(self):
        category = app.public_category(["Fiction", "Fantasy"], "Sem_classificacao_confiavel")
        self.assertEqual(category, "800-Literatura > Fantasia")

    def test_google_books_preenche_isbn(self):
        original_fetch = app.fetch_json
        app.fetch_json = lambda url: ({
            "items": [{
                "id": "volume-teste",
                "volumeInfo": {
                    "title": "O Lado Mais Sombrio",
                    "authors": ["A. G. Howard"],
                    "publishedDate": "2014-01-01",
                    "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780000000002"}],
                    "publisher": "Editora Teste",
                    "language": "pt",
                    "categories": ["Fiction", "Fantasy"],
                },
            }],
        }, "")
        try:
            row = {
                "titulo_detectado": "O Lado Mais Sombrio",
                "autor_detectado": "A. G. Howard",
            }
            result, completed = app.google_books_lookup(row, {"google_books": True})
        finally:
            app.fetch_json = original_fetch
        self.assertTrue(completed)
        self.assertIsNotNone(result)
        self.assertEqual(result["isbn_13"], "9780000000002")

    def test_destino_usa_autor_em_vez_de_categoria(self):
        row = {
            "autor_detectado": "A. G. Howard",
            "titulo_detectado": "O Lado Mais Sombrio",
            "ano": "",
            "arquivo_original": "origem.pdf",
            "tipo": "Livros_e_Manuais",
            "categoria": "800-Literatura > Fantasia",
        }
        self.assertEqual(
            app.unique_destination(row, set()),
            "Livros/A/A. G. Howard/A. G. Howard - O Lado Mais Sombrio.pdf",
        )

    def test_nome_do_arquivo_recupera_titulo_quando_pdf_tem_copyright(self):
        row = {
            "arquivo_original": "Audrey Carlan - A Garota do Calendário - 05 - Maio.pdf",
            "titulo_detectado": "DADOS DE COPYRIGHT",
            "autor_detectado": "Audrey Carlan",
        }
        variants = app.bibliographic_query_variants(row)
        self.assertEqual(variants[0]["titulo_detectado"], "A Garota do Calendário - 05 - Maio")
        self.assertEqual(variants[0]["autor_detectado"], "Audrey Carlan")

    def test_acerto_da_versao_anterior_e_reaproveitado(self):
        row = {
            "arquivo_original": "Autor - Livro.pdf",
            "titulo_detectado": "Livro",
            "autor_detectado": "Autor",
            "status": "UNICO",
            "tipo": "Livros_e_Manuais",
            "ano": "",
            "categoria": "Sem_classificacao_confiavel",
        }
        metadata = {
            "title": "Livro",
            "authors": ["Autor"],
            "year": "2020",
            "source": "Open Library",
            "score": 1.0,
        }
        with TemporaryDirectory() as directory:
            report_dir = Path(directory)
            legacy = {app.legacy_cache_key(row): {"status": "match", "metadata": metadata}}
            (report_dir / app.CACHE_FILENAME).write_text(app.json.dumps(legacy), encoding="utf-8")
            app.enrich_rows([row], report_dir, delay=0)
        self.assertEqual(row["fonte_metadados"], "Open Library")
        self.assertEqual(row["ano"], "2020")


if __name__ == "__main__":
    unittest.main()

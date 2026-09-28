import unittest

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


if __name__ == "__main__":
    unittest.main()

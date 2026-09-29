#!/usr/bin/env python3
"""Organizador seguro de bibliotecas PDF.

Etapa 1 (padrao): analisa os PDFs e gera inventario.csv, plano_organizacao.csv
e relatorio.html. Nao renomeia, move ou apaga nenhum arquivo.

Etapa 2 (--aplicar): copia somente os PDFs unicos para uma nova pasta
Biblioteca_Organizada. Os originais permanecem intocados.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Dependencia ausente: PyMuPDF. Execute 01_ANALISAR_PDFS.bat.", file=sys.stderr)
    sys.exit(2)


APP_DIR = "__PDF_ORGANIZACAO__"
LIBRARY_DIR = "Biblioteca_Organizada"
CSV_FIELDS = [
    "id", "arquivo_original", "tamanho_mb", "paginas", "titulo_detectado", "autor_detectado",
    "ano", "isbn_13", "isbn_10", "editora", "idioma", "categorias_publicas", "descricao_curta",
    "fonte_metadados", "confianca_metadados", "url_catalogo", "doi_detectado", "categoria", "tipo",
    "confianca", "status", "grupo_duplicado", "destino_sugerido", "observacao",
]

# As regras servem para a primeira classificacao. Depois da analise, elas podem ser
# ajustadas sem tocar nos PDFs.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "Engenharia_Eletrica_e_Energia": (
        "engenharia eletrica", "electrical engineering", "power system", "sistema de potencia",
        "subestacao", "substation", "circuitos eletricos", "circuit analysis", "energia solar",
        "photovoltaic", "energia renovavel", "renewable energy", "alta tensao", "high voltage",
        "transformador", "transformer", "aterramento", "grounding",
    ),
    "Automacao_e_Controle": (
        "automacao", "automation", "plc", "clp", "scada", "controle industrial", "industrial control",
        "control systems", "sistemas de controle", "instrumentacao", "instrumentation", "robotica", "robotics",
        "mechatronics", "industria 4.0", "industry 4.0",
    ),
    "Telecom_Redes_e_TI": (
        "telecomunicacao", "telecomunicacoes", "telecommunication", "wireless", "radio frequency", "rf", "antena", "antenna",
        "redes de computadores", "computer networks", "networking", "fiber optic", "fibra optica", "mikrotik",
        "linux", "cybersecurity", "seguranca da informacao", "internet protocol", "tcp/ip",
    ),
    "Programacao_e_Computacao": (
        "programacao", "programming", "software engineering", "python", "javascript", "java", "c++",
        "algoritmos", "algorithms", "database", "banco de dados", "machine learning", "artificial intelligence",
        "inteligencia artificial", "web development", "desenvolvimento web",
    ),
    "Engenharia_Mecanica_Construcao_e_Arquitetura": (
        "engenharia mecanica", "mechanical engineering", "civil engineering", "engenharia civil", "concreto",
        "concrete", "structural", "estrutura", "arquitetura", "architecture", "manufacturing",
        "manufatura", "soldagem", "welding",
    ),
    "Matematica_Fisica_e_Ciencias": (
        "matematica", "mathematics", "calculus", "calculo", "algebra", "estatistica", "statistics",
        "physics", "fisica", "chemistry", "quimica", "biology", "biologia", "astronomy", "astronomia",
    ),
    "Gestao_Negocios_e_Projetos": (
        "gestao de projetos", "project management", "pmbok", "agile", "scrum", "management",
        "administracao", "administration", "business", "negociacao", "negotiation", "leadership",
        "lideranca", "empreendedorismo", "entrepreneurship", "economia", "economics",
    ),
    "Direito_e_Politica": (
        "direito", "law ", "legal", "juridic", "constituicao", "constitution", "legislacao", "legislation",
        "politica", "politics", "administracao publica", "public administration",
    ),
    "Medicina_e_Saude": (
        "medicina", "medicine", "clinical", "clinica", "saude", "health", "nursing", "enfermagem",
        "psicologia", "psychology", "farmacologia", "pharmacology", "nutrition", "nutricao",
    ),
    "Historia_Filosofia_e_Humanas": (
        "historia", "history", "filosofia", "philosophy", "sociologia", "sociology", "antropologia",
        "anthropology", "geografia", "geography", "educacao", "education", "linguistica", "linguistics",
    ),
    "Literatura_e_Artes": (
        "romance", "novel", "poesia", "poetry", "literatura", "literature", "cinema", "fotografia",
        "photography", "musica", "music", "design", "artes", "arts",
    ),
}

GENERIC_TITLES = {
    "untitled", "sem titulo", "microsoft word", "document", "none", "",
    "dados de copyright", "copyright", "pagina de rosto", "sumario", "indice",
}
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
YEAR_RE = re.compile(r"\b(19[0-9]{2}|20[0-2][0-9])\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:a-z0-9]+\b", re.IGNORECASE)
CACHE_FILENAME = "cache_metadados_publicos.json"


def ascii_fold(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c)
    )


def compact(value: str, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:limit].rstrip(" .-_")


def safe_component(value: str, fallback: str, limit: int = 140) -> str:
    value = INVALID_FILENAME.sub(" ", compact(value, limit))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or fallback


def choose_folder() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Selecione a pasta que contem seus PDFs")
        root.destroy()
        return Path(selected) if selected else None
    except Exception as exc:
        print(f"Nao foi possivel abrir o seletor de pasta: {exc}", file=sys.stderr)
        return None


def useful_title(value: str) -> bool:
    normalized = ascii_fold(compact(value))
    return len(normalized) >= 5 and normalized not in GENERIC_TITLES and not normalized.startswith("http")


def title_from_text(text: str, fallback: str) -> str:
    candidates = []
    for line in text.splitlines()[:80]:
        line = compact(line, 180)
        folded = ascii_fold(line)
        if not (8 <= len(line) <= 180 and sum(c.isalpha() for c in line) >= 5):
            continue
        if any(word in folded for word in ("abstract", "resumo", "keywords", "palavras-chave", "doi:", "issn")):
            continue
        if re.fullmatch(r"[\d .,:;()\-]+", line):
            continue
        candidates.append(line)
    return candidates[0] if candidates else fallback


def author_from_metadata(value: str) -> str:
    value = compact(value, 100)
    if not value or ascii_fold(value) in {"unknown", "anonymous", "none"}:
        return "Autor desconhecido"
    return value


def keyword_matches(text: str, keyword: str) -> int:
    """Conta termos completos, evitando falsos positivos como CAD em 'cada'."""
    expression = r"(?<!\w)" + re.escape(ascii_fold(keyword)) + r"(?!\w)"
    return len(re.findall(expression, text))


def classify(text: str) -> tuple[str, int]:
    """Retorna apenas assunto com evidência suficiente.

    A classificação por assunto é só uma sugestão do relatório: ela não decide
    a pasta final, pois palavras no miolo de romances podem parecer técnicas.
    """
    folded = ascii_fold(text)
    scores = {
        category: sum(keyword_matches(folded, keyword) for keyword in keywords)
        for category, keywords in CATEGORIES.items()
    }
    category, score = max(scores.items(), key=lambda item: item[1])
    if score < 3:
        return "Sem_classificacao_confiavel", score
    return category, score


def normalized_bibliographic_text(value: str) -> str:
    """Normaliza um texto para comparar título e autor, não para exibir."""
    return " ".join(re.findall(r"[a-z0-9]+", ascii_fold(value)))


def similarity(left: str, right: str) -> float:
    left, right = normalized_bibliographic_text(left), normalized_bibliographic_text(right)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def metadata_score(row: dict[str, str], candidate_title: str, candidate_authors: list[str]) -> float:
    title_score = similarity(row["titulo_detectado"], candidate_title)
    expected_author = row.get("autor_detectado", "")
    if ascii_fold(expected_author) in {"", "autor desconhecido", "unknown"}:
        return title_score
    author_score = max((similarity(expected_author, author) for author in candidate_authors), default=0.0)
    return title_score * 0.78 + author_score * 0.22


def public_category(subjects: list[str], fallback: str) -> str:
    """Converte assuntos públicos em uma classificação ampla, inspirada na CDD."""
    text = ascii_fold(" | ".join(subjects))
    rules = (
        (("science fiction", "ficcao cientifica", "dystopian", "distopia"), "800-Literatura > Ficcao_Cientifica"),
        (("fantasy", "fantasia", "magic", "magia"), "800-Literatura > Fantasia"),
        (("mystery", "detective", "thriller", "suspense", "crime fiction", "horror", "terror"), "800-Literatura > Misterio_Suspense_Terror"),
        (("juvenile fiction", "young adult", "children", "infantil", "adolescente"), "800-Literatura > Infantojuvenil"),
        (("romance fiction", "love stories", "romance"), "800-Literatura > Romance"),
        (("fiction", "literature", "literatura", "novel", "short stories"), "800-Literatura > Ficcao_Geral"),
        (("comics", "graphic novels", "manga", "quadrinhos"), "741-Artes > Quadrinhos_e_Manga"),
        (("religion", "christian", "bible", "espiritismo", "religiao"), "200-Religiao_e_Espiritualidade"),
        (("biography", "autobiography", "memoir", "biografia", "memorias"), "920-Biografias"),
        (("history", "historia", "geography", "geografia"), "900-Historia_e_Geografia"),
        (("law", "legal", "direito", "politics", "politica"), "340-Direito_e_Politica"),
        (("business", "management", "project management", "negocios", "gestao"), "650-Gestao_e_Negocios"),
        (("computer", "programming", "software", "computacao", "programacao"), "005-Computacao_e_Programacao"),
        (("telecommunication", "networking", "telecomunicacoes", "redes"), "621.38-Telecomunicacoes_e_Redes"),
        (("electrical engineering", "electric power", "engenharia eletrica", "energia"), "621.3-Engenharia_Eletrica_e_Energia"),
        (("automation", "control systems", "automacao", "robotics", "robotica"), "629.8-Automacao_e_Controle"),
        (("medicine", "health", "medical", "saude", "medicina"), "610-Saude_e_Medicina"),
        (("mathematics", "physics", "chemistry", "matematica", "fisica", "quimica"), "500-Ciencias_e_Matematica"),
    )
    for terms, category in rules:
        if any(term in text for term in terms):
            return category
    return fallback


def first_year(value: Any) -> str:
    match = YEAR_RE.search(str(value or ""))
    return match.group(1) if match else ""


def first_isbn(values: list[str] | None, length: int) -> str:
    for value in values or []:
        digits = re.sub(r"[^0-9Xx]", "", str(value))
        if len(digits) == length:
            return digits.upper()
    return ""


def short_description(value: str) -> str:
    value = compact(re.sub(r"<[^>]+>", " ", value or ""), 450)
    return value


def detected_doi(text: str) -> str:
    match = DOI_RE.search(text or "")
    return match.group(0).rstrip(".,;:)") if match else ""


def fetch_json(url: str) -> tuple[dict[str, Any] | None, str]:
    """Faz uma consulta pública, sem enviar o PDF ou o seu conteúdo."""
    request = Request(url, headers={"User-Agent": "OrganizadorBibliotecaPDF/3.0 (catalogacao-local)"})
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except URLError as exc:
        return None, f"Rede: {getattr(exc, 'reason', 'indisponivel')}"
    except (TimeoutError, json.JSONDecodeError) as exc:
        return None, type(exc).__name__


def known_author(row: dict[str, str]) -> bool:
    return ascii_fold(row.get("autor_detectado", "")) not in {"", "autor desconhecido", "unknown"}


def accepted_score(row: dict[str, str], score: float) -> bool:
    return score >= (0.72 if known_author(row) else 0.86)


def filename_bibliographic_guess(row: dict[str, str]) -> tuple[str, str]:
    """Obtém título e autor do nome do arquivo quando ele segue Autor - Título.

    Muitos PDFs foram salvos com um nome bibliograficamente melhor que a primeira
    página extraída: capa, aviso de copyright e sumário frequentemente aparecem
    antes do título. O dado é usado apenas como alternativa de busca, nunca como
    uma confirmação automática.
    """
    original = Path(row.get("arquivo_original", "")).stem.replace("_", " ")
    original = re.sub(r"\s*\((?:\d+|copia)\)\s*$", "", original, flags=re.IGNORECASE)
    original = compact(original, 260)
    parts = re.split(r"\s+-\s+", original, maxsplit=1)
    if len(parts) == 2 and useful_title(parts[1]) and len(parts[0]) >= 2:
        return compact(parts[1], 180), compact(parts[0], 100)
    return compact(original, 180), compact(row.get("autor_detectado", ""), 100)


def search_title_variants(title: str) -> list[str]:
    """Retorna poucas variações seguras para uma busca bibliográfica."""
    title = compact(title, 180)
    variants = [title]
    # Catálogos divergem entre título completo, subtítulo e indicação de volume.
    without_parenthetical = compact(re.sub(r"\s*[\[(][^\]\)]{1,90}[\])]\s*", " ", title), 180)
    if useful_title(without_parenthetical):
        variants.append(without_parenthetical)
    for separator in (":", " | "):
        if separator in title:
            main_title = compact(title.split(separator, 1)[0], 180)
            if useful_title(main_title):
                variants.append(main_title)
    unique: list[str] = []
    for value in variants:
        if useful_title(value) and normalized_bibliographic_text(value) not in {
            normalized_bibliographic_text(existing) for existing in unique
        }:
            unique.append(value)
    return unique[:3]


def bibliographic_query_variants(row: dict[str, str]) -> list[dict[str, str]]:
    """Monta consultas alternativas sem alterar os dados locais do PDF."""
    current_title = compact(row.get("titulo_detectado", ""), 180)
    current_author = compact(row.get("autor_detectado", ""), 100)
    file_title, file_author = filename_bibliographic_guess(row)
    bases: list[tuple[str, str]] = []
    # Quando o texto extraído é genérico, o nome estruturado do arquivo é a fonte
    # mais confiável para começar. Nos demais casos preservamos a ordem original.
    if not useful_title(current_title) and useful_title(file_title):
        bases.append((file_title, file_author))
    if useful_title(current_title):
        bases.append((current_title, current_author))
    if useful_title(file_title):
        bases.append((file_title, file_author))

    variants: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for title, author in bases:
        for title_variant in search_title_variants(title):
            normalized = (
                normalized_bibliographic_text(title_variant),
                normalized_bibliographic_text(author),
            )
            if normalized in seen:
                continue
            seen.add(normalized)
            query_row = dict(row)
            query_row["titulo_detectado"] = title_variant
            query_row["autor_detectado"] = author or row.get("autor_detectado", "")
            variants.append(query_row)
    return variants[:4] or [dict(row)]


def google_books_lookup(row: dict[str, str], state: dict[str, bool]) -> tuple[dict[str, Any] | None, bool]:
    if not state.get("google_books", True):
        return None, False
    title = row["titulo_detectado"]
    author = row.get("autor_detectado", "")
    terms = [f'intitle:"{title}"']
    if known_author(row):
        terms.append(f'inauthor:"{author}"')
    api_key = os.environ.get("GOOGLE_BOOKS_API_KEY", "").strip()
    best: tuple[float, dict[str, Any]] | None = None
    # O segundo formato é menos rígido e recupera títulos com subtítulo,
    # pontuação ou transliteração diferentes no catálogo do Google.
    queries = [" ".join(terms), " ".join(filter(None, [title, author if known_author(row) else ""]))]
    for query in dict.fromkeys(queries):
        params: dict[str, str | int] = {"q": query, "maxResults": 8, "printType": "books"}
        if api_key:
            params["key"] = api_key
        data, error = fetch_json("https://www.googleapis.com/books/v1/volumes?" + urlencode(params))
        if data is None:
            if error in {"HTTP 403", "HTTP 429"}:
                state["google_books"] = False
                state["google_books_error"] = error
                print("  Google Books indisponível nesta sessão; continuando com Open Library.")
            return None, False
        for item in data.get("items", []):
            info = item.get("volumeInfo", {})
            candidate_title = str(info.get("title", ""))
            authors = [str(candidate_author) for candidate_author in info.get("authors", [])]
            score = metadata_score(row, candidate_title, authors)
            if best is None or score > best[0]:
                identifiers = {entry.get("type"): entry.get("identifier") for entry in info.get("industryIdentifiers", [])}
                best = (score, {
                    "title": candidate_title,
                    "authors": authors,
                    "year": first_year(info.get("publishedDate")),
                    "isbn_13": str(identifiers.get("ISBN_13", "")),
                    "isbn_10": str(identifiers.get("ISBN_10", "")),
                    "publisher": str(info.get("publisher", "")),
                    "language": str(info.get("language", "")),
                    "subjects": [str(value) for value in info.get("categories", [])],
                    "description": short_description(str(info.get("description", ""))),
                    "source": "Google Books",
                    "url": str(info.get("infoLink") or f"https://books.google.com/books?id={item.get('id', '')}"),
                    "score": score,
                })
    return (best[1] if best and accepted_score(row, best[0]) else None), True


def open_library_lookup(row: dict[str, str]) -> tuple[dict[str, Any] | None, bool]:
    best: tuple[float, dict[str, Any]] | None = None
    fields = "key,title,author_name,first_publish_year,isbn,subject,publisher,language"
    precise_query: dict[str, str | int] = {"title": row["titulo_detectado"], "limit": 8, "fields": fields}
    if known_author(row):
        precise_query["author"] = row["autor_detectado"]
    broad_query: dict[str, str | int] = {
        "q": " ".join(filter(None, [row["titulo_detectado"], row.get("autor_detectado", "") if known_author(row) else ""])),
        "limit": 12,
        "fields": fields,
    }
    for params in (precise_query, broad_query):
        data, error = fetch_json("https://openlibrary.org/search.json?" + urlencode(params))
        if data is None:
            return None, False
        for item in data.get("docs", []):
            title = str(item.get("title", ""))
            authors = [str(author) for author in item.get("author_name", [])]
            score = metadata_score(row, title, authors)
            if best is None or score > best[0]:
                isbns = [str(value) for value in item.get("isbn", [])]
                key = str(item.get("key", ""))
                best = (score, {
                    "title": title,
                    "authors": authors,
                    "year": first_year(item.get("first_publish_year")),
                    "isbn_13": first_isbn(isbns, 13),
                    "isbn_10": first_isbn(isbns, 10),
                    "publisher": str((item.get("publisher") or [""])[0]),
                    "language": str((item.get("language") or [""])[0]),
                    "subjects": [str(value) for value in (item.get("subject") or [])[:8]],
                    "description": "",
                    "source": "Open Library",
                    "url": f"https://openlibrary.org{key}" if key else "",
                    "score": score,
                })
    return (best[1] if best and accepted_score(row, best[0]) else None), True


def crossref_lookup(row: dict[str, str]) -> tuple[dict[str, Any] | None, bool]:
    doi = row.get("doi_detectado", "")
    if doi:
        url = "https://api.crossref.org/works/" + quote(doi, safe="")
        data, error = fetch_json(url)
        items = [data.get("message", {})] if data else []
    else:
        citation = " ".join(filter(None, [row["titulo_detectado"], row.get("autor_detectado", "")]))
        data, error = fetch_json("https://api.crossref.org/works?" + urlencode({"query.bibliographic": citation, "rows": 3}))
        items = data.get("message", {}).get("items", []) if data else []
    if data is None:
        return None, False
    best: tuple[float, dict[str, Any]] | None = None
    for item in items:
        title = str((item.get("title") or [""])[0])
        authors = [" ".join(filter(None, [str(author.get("given", "")), str(author.get("family", ""))])).strip() for author in item.get("author", [])]
        score = metadata_score(row, title, authors)
        if best is None or score > best[0]:
            parts = item.get("published", {}).get("date-parts", [[""]])
            year = str(parts[0][0]) if parts and parts[0] else ""
            crossref_doi = str(item.get("DOI", doi))
            best = (score, {
                "title": title,
                "authors": authors,
                "year": year,
                "isbn_13": "",
                "isbn_10": "",
                "publisher": str(item.get("publisher", "")),
                "language": str(item.get("language", "")),
                "subjects": [str(value) for value in item.get("subject", [])] or ["Artigo científico"],
                "description": "",
                "source": "Crossref",
                "url": f"https://doi.org/{crossref_doi}" if crossref_doi else "",
                "score": score,
                "doi": crossref_doi,
            })
    return (best[1] if best and accepted_score(row, best[0]) else None), True


def lookup_public_metadata(row: dict[str, str], state: dict[str, bool]) -> tuple[dict[str, Any] | None, bool]:
    """Consulta fontes públicas com variações seguras de título e autor."""
    any_success = False
    candidates = bibliographic_query_variants(row)
    if row.get("tipo") == "Artigos":
        for candidate in candidates:
            match, success = crossref_lookup(candidate)
            any_success = any_success or success
            if match:
                return match, any_success
    for candidate in candidates:
        match, success = google_books_lookup(candidate, state)
        any_success = any_success or success
        if match:
            return match, any_success
        if not state.get("google_books", True):
            break
    for candidate in candidates:
        match, success = open_library_lookup(candidate)
        any_success = any_success or success
        if match:
            return match, any_success
    return None, any_success


def cache_key(row: dict[str, str]) -> str:
    return "v4|" + "|".join((row.get("tipo", ""), normalized_bibliographic_text(row.get("titulo_detectado", "")), normalized_bibliographic_text(row.get("autor_detectado", ""))))


def legacy_cache_key(row: dict[str, str]) -> str:
    """Chave da versão anterior, usada apenas para reaproveitar acertos válidos."""
    return "v3|" + "|".join((row.get("tipo", ""), normalized_bibliographic_text(row.get("titulo_detectado", "")), normalized_bibliographic_text(row.get("autor_detectado", ""))))


def load_metadata_cache(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_metadata_cache(path: Path, cache: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def apply_public_metadata(row: dict[str, str], metadata: dict[str, Any]) -> None:
    row["titulo_detectado"] = compact(str(metadata.get("title") or row["titulo_detectado"]), 180)
    authors = [compact(str(author), 100) for author in metadata.get("authors", []) if compact(str(author), 100)]
    if authors:
        row["autor_detectado"] = compact("; ".join(authors), 100)
    row["ano"] = str(metadata.get("year") or row.get("ano", ""))
    row["isbn_13"] = str(metadata.get("isbn_13", ""))
    row["isbn_10"] = str(metadata.get("isbn_10", ""))
    row["editora"] = compact(str(metadata.get("publisher", "")), 120)
    row["idioma"] = compact(str(metadata.get("language", "")), 30)
    subjects = [compact(str(subject), 80) for subject in metadata.get("subjects", []) if compact(str(subject), 80)]
    row["categorias_publicas"] = " | ".join(subjects[:8])
    row["descricao_curta"] = short_description(str(metadata.get("description", "")))
    row["fonte_metadados"] = str(metadata.get("source", ""))
    row["confianca_metadados"] = f"{float(metadata.get('score', 0)):.2f}"
    row["url_catalogo"] = str(metadata.get("url", ""))
    row["doi_detectado"] = str(metadata.get("doi") or row.get("doi_detectado", ""))
    row["categoria"] = public_category(subjects, row.get("categoria", "Sem_classificacao_confiavel"))


def enrich_rows(rows: list[dict[str, str]], report_dir: Path, delay: float, retry_missing: bool = False) -> None:
    """Preenche metadados externos com cache e retomada segura."""
    report_dir.mkdir(parents=True, exist_ok=True)
    cache_path = report_dir / CACHE_FILENAME
    cache = load_metadata_cache(cache_path)
    state = {"google_books": True}
    candidates = [row for row in rows if row.get("status") != "DUPLICADO"]
    matched = cached = migrated = retried = 0
    print(f"Consultando catálogos públicos para {len(candidates)} itens. Isso pode demorar; é possível interromper e retomar depois.")
    for index, row in enumerate(candidates, 1):
        for field in CSV_FIELDS:
            row.setdefault(field, "")
        key = cache_key(row)
        entry = cache.get(key)
        # A versão anterior guardava "não encontrado" depois de uma única
        # tentativa. Os acertos continuam confiáveis e são migrados; as lacunas
        # voltam a ser pesquisadas com as variações novas.
        if entry is None:
            old_entry = cache.get(legacy_cache_key(row))
            if old_entry and old_entry.get("status") == "match":
                entry = old_entry
                cache[key] = old_entry
                migrated += 1
        if entry is not None and not (retry_missing and entry.get("status") == "not_found"):
            cached += 1
            if entry.get("status") == "match":
                apply_public_metadata(row, entry["metadata"])
                matched += 1
        else:
            if entry is not None:
                retried += 1
            metadata, completed = lookup_public_metadata(row, state)
            if metadata:
                cache[key] = {"status": "match", "metadata": metadata, "checked_at": datetime.now().isoformat(timespec="seconds")}
                apply_public_metadata(row, metadata)
                matched += 1
            elif completed:
                cache[key] = {"status": "not_found", "checked_at": datetime.now().isoformat(timespec="seconds")}
            if index % 10 == 0 or index == len(candidates):
                save_metadata_cache(cache_path, cache)
            if delay > 0:
                time.sleep(delay)
        if index == 1 or index % 25 == 0 or index == len(candidates):
            print(f"  {index}/{len(candidates)} — encontrados: {matched}; reaproveitados do cache: {cached}")
    save_metadata_cache(cache_path, cache)
    if migrated:
        print(f"  {migrated} acertos da versão anterior foram reaproveitados.")
    if retried:
        print(f"  {retried} lacunas anteriores foram consultadas novamente.")
    if not state.get("google_books", True):
        print("  Google Books não respondeu nesta sessão. Uma chave gratuita pode ampliar a cobertura na próxima tentativa.")


def assign_destinations(rows: list[dict[str, str]]) -> None:
    used_destinations: set[str] = set()
    for row in rows:
        row["destino_sugerido"] = unique_destination(row, used_destinations) if row.get("status") == "UNICO" else ""


def detect_type(text: str, pages: int, filename: str) -> str:
    folded = ascii_fold(text + " " + filename)
    article_markers = ("abstract", "resumo", "doi", "keywords", "palavras-chave", "journal", "vol.", "issue")
    if any(marker in folded for marker in article_markers) and pages <= 80:
        return "Artigos"
    return "Livros_e_Manuais"


def extract_pdf(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"pages": "", "title": path.stem, "author": "Autor desconhecido", "year": "", "text": "", "error": ""}
    try:
        with fitz.open(path) as document:
            result["pages"] = document.page_count
            metadata = document.metadata or {}
            text_parts: list[str] = []
            for page_number in range(min(3, document.page_count)):
                page_text = document.load_page(page_number).get_text("text")
                text_parts.append(page_text[:25000])
            text = "\n".join(text_parts)
            meta_title = compact(metadata.get("title") or "")
            result["title"] = meta_title if useful_title(meta_title) else title_from_text(text, path.stem)
            result["author"] = author_from_metadata(metadata.get("author") or "")
            result["text"] = text
            years = YEAR_RE.findall(" ".join([str(metadata), text[:12000], path.stem]))
            if years:
                result["year"] = years[-1]
    except Exception as exc:
        result["error"] = f"Nao foi possivel ler: {type(exc).__name__}"
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def author_initial(author: str) -> str:
    for character in ascii_fold(author):
        if character.isalpha() or character.isdigit():
            return character.upper()
    return "_"


def unique_destination(row: dict[str, str], used: set[str]) -> str:
    author = safe_component(row["autor_detectado"], "Autor desconhecido", 55)
    title = safe_component(row["titulo_detectado"], Path(row["arquivo_original"]).stem, 120)
    year = f" ({row['ano']})" if row["ano"] else ""
    base = safe_component(f"{author} - {title}{year}", "PDF", 170)
    # Autor e título são os dados extraídos com maior confiabilidade nesta
    # coleção. A categoria é ignorada para não enviar um romance a uma pasta
    # técnica por causa de uma palavra no texto do PDF.
    collection = "Artigos" if row["tipo"] == "Artigos" else "Livros"
    parent = Path(collection) / author_initial(author) / author
    candidate = parent / f"{base}.pdf"
    number = 2
    while str(candidate).casefold() in used:
        candidate = parent / f"{base} [{number}].pdf"
        number += 1
    used.add(str(candidate).casefold())
    return str(candidate)


def pdf_files(source: Path) -> list[Path]:
    excluded = {APP_DIR.casefold(), LIBRARY_DIR.casefold()}
    found: list[Path] = []
    for root, dirs, files in os.walk(source):
        dirs[:] = [directory for directory in dirs if directory.casefold() not in excluded]
        for filename in files:
            if filename.lower().endswith(".pdf"):
                found.append(Path(root) / filename)
    return sorted(found, key=lambda item: str(item).casefold())


def make_report(source: Path, rows: list[dict[str, str]], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = report_dir / "inventario.csv"
    plan_path = report_dir / "plano_organizacao.csv"
    for path in (inventory_path, plan_path):
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    category_counts = Counter(row["categoria"] for row in rows)
    status_counts = Counter(row["status"] for row in rows)
    duplicate_count = sum(1 for row in rows if row["status"] == "DUPLICADO")
    unreadable_count = sum(1 for row in rows if row["status"] == "NAO_LIDO")
    enriched_count = sum(1 for row in rows if row.get("fonte_metadados"))
    isbn_count = sum(1 for row in rows if row.get("isbn_13") or row.get("isbn_10"))
    source_counts = Counter(row["fonte_metadados"] for row in rows if row.get("fonte_metadados"))
    rows_html = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in CSV_FIELDS) + "</tr>"
        for row in rows
    )
    category_html = "".join(
        f"<tr><td>{html.escape(category)}</td><td>{count}</td></tr>" for category, count in category_counts.most_common()
    )
    source_html = "".join(
        f"<tr><td>{html.escape(source)}</td><td>{count}</td></tr>" for source, count in source_counts.most_common()
    ) or "<tr><td colspan=\"2\">Nenhuma consulta pública realizada ainda.</td></tr>"
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    source_escaped = html.escape(str(source))
    report = f"""<!doctype html>
<html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><title>Relatorio da biblioteca PDF</title>
<style>
body{{font:14px Segoe UI,Arial,sans-serif;color:#1f2937;margin:32px;background:#f7f8fa}} h1{{color:#173b5c}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#fff;border-left:5px solid #2f6f9f;padding:14px 18px;min-width:150px;border-radius:4px;box-shadow:0 1px 4px #d7dce1}}.n{{font-size:28px;font-weight:700}}
table{{border-collapse:collapse;background:white;width:100%;margin:18px 0}}th,td{{border:1px solid #d7dce1;padding:7px;text-align:left;vertical-align:top}}th{{background:#173b5c;color:#fff;position:sticky;top:0}}tr:nth-child(even){{background:#f4f7f9}}.wide{{overflow:auto;max-height:67vh}}
code{{background:#edf2f7;padding:2px 5px}}
</style></head><body>
<h1>Inventario da biblioteca PDF</h1><p>Gerado em {generated}. Pasta analisada: <code>{source_escaped}</code>.</p>
<div class=\"cards\"><div class=\"card\"><div class=\"n\">{len(rows)}</div>PDFs encontrados</div><div class=\"card\"><div class=\"n\">{duplicate_count}</div>duplicados exatos</div><div class=\"card\"><div class=\"n\">{unreadable_count}</div>nao lidos</div><div class=\"card\"><div class=\"n\">{enriched_count}</div>metadados públicos encontrados</div><div class=\"card\"><div class=\"n\">{isbn_count}</div>com ISBN</div><div class=\"card\"><div class=\"n\">{status_counts.get('UNICO', 0)}</div>prontos para copiar</div></div>
<h2>Consulta a catálogos públicos</h2><p>Quando executada, a busca envia apenas título, autor e DOI detectado — nunca o PDF ou o texto do livro. O resultado pode trazer ISBN, editora, idioma, descrição e categorias.</p><table><thead><tr><th>Fonte</th><th>Registros aproveitados</th></tr></thead><tbody>{source_html}</tbody></table>
<h2>Assuntos detectados</h2><table><thead><tr><th>Categoria</th><th>Quantidade</th></tr></thead><tbody>{category_html}</tbody></table>
<h2>Como usar este resultado</h2><ol><li>Execute <code>03_ENRIQUECER_CATALOGO.bat</code> para completar os dados por consulta pública.</li><li>Revise este relatorio e o arquivo <code>plano_organizacao.csv</code>.</li><li>Se estiver de acordo, execute <code>02_CRIAR_BIBLIOTECA_SEGURA.bat</code>.</li><li>Ele apenas cria copias; seus originais não são alterados.</li></ol>
<p><strong>Estrutura criada:</strong> <code>Livros\\Inicial do autor\\Autor\\Titulo (Ano).pdf</code>. Os artigos detectados seguem a mesma ideia em <code>Artigos</code>. A coluna <em>categoria</em> é apenas uma sugestão e não muda a localização.</p>
<h2>Detalhamento</h2><div class=\"wide\"><table><thead><tr>{''.join(f'<th>{html.escape(column)}</th>' for column in CSV_FIELDS)}</tr></thead><tbody>{rows_html}</tbody></table></div>
</body></html>"""
    (report_dir / "relatorio.html").write_text(report, encoding="utf-8")


def analyse(source: Path, enrich: bool = False, delay: float = 0.55, retry_missing: bool = False) -> int:
    source = source.resolve()
    report_dir = source / APP_DIR
    files = pdf_files(source)
    if not files:
        print("Nenhum PDF foi encontrado na pasta selecionada.")
        return 1
    print(f"Encontrados {len(files)} PDFs. Lendo metadados e as primeiras paginas...")
    sizes: dict[int, list[Path]] = defaultdict(list)
    for path in files:
        try:
            sizes[path.stat().st_size].append(path)
        except OSError:
            pass
    hash_groups: dict[str, list[Path]] = defaultdict(list)
    candidates = [path for group in sizes.values() if len(group) > 1 for path in group]
    if candidates:
        print(f"Verificando {len(candidates)} arquivos que podem ser duplicados exatos...")
    for path in candidates:
        try:
            hash_groups[sha256(path)].append(path)
        except OSError:
            continue
    duplicate_by_path: dict[Path, tuple[int, bool]] = {}
    group_id = 0
    for group in hash_groups.values():
        if len(group) > 1:
            group_id += 1
            for index, path in enumerate(group):
                duplicate_by_path[path] = (group_id, index == 0)

    rows: list[dict[str, str]] = []
    for index, path in enumerate(files, 1):
        if index == 1 or index % 25 == 0 or index == len(files):
            print(f"  {index}/{len(files)}: {path.name[:75]}")
        info = extract_pdf(path)
        try:
            size_mb = f"{path.stat().st_size / (1024 * 1024):.2f}"
        except OSError:
            size_mb = ""
        text_for_classification = " ".join([path.stem, info["title"], info["author"], info["text"]])
        category, score = classify(text_for_classification)
        kind = detect_type(text_for_classification, int(info["pages"] or 0), path.name)
        status = "UNICO"
        group = ""
        observation = info["error"]
        if info["error"]:
            status = "NAO_LIDO"
            observation = (observation + "; classificado apenas pelo nome do arquivo").strip("; ")
        if path in duplicate_by_path:
            duplicate_group, is_first = duplicate_by_path[path]
            group = str(duplicate_group)
            if not is_first:
                status = "DUPLICADO"
                observation = f"Copia exata do grupo {duplicate_group}; nao sera copiada para a nova biblioteca."
        row = {
            "id": str(index), "arquivo_original": str(path.relative_to(source)), "tamanho_mb": size_mb,
            "paginas": str(info["pages"]), "titulo_detectado": compact(info["title"], 180),
            "autor_detectado": compact(info["author"], 100), "ano": str(info["year"]),
            "isbn_13": "", "isbn_10": "", "editora": "", "idioma": "", "categorias_publicas": "",
            "descricao_curta": "", "fonte_metadados": "", "confianca_metadados": "", "url_catalogo": "",
            "doi_detectado": detected_doi(info["text"]), "categoria": category, "tipo": kind,
            "confianca": str(score), "status": status,
            "grupo_duplicado": group, "destino_sugerido": "", "observacao": observation,
        }
        rows.append(row)
    if enrich:
        enrich_rows(rows, report_dir, delay, retry_missing=retry_missing)
    assign_destinations(rows)
    make_report(source, rows, report_dir)
    print("\nAnalise concluida sem alterar nenhum PDF.")
    print(f"Abra o relatorio: {report_dir / 'relatorio.html'}")
    if not enrich:
        print("Para preencher ISBN, editora e categorias públicas, execute 03_ENRIQUECER_CATALOGO.bat.")
    print("Depois de conferir, execute 02_CRIAR_BIBLIOTECA_SEGURA.bat.")
    return 0


def enrich_existing(source: Path, delay: float = 0.55, retry_missing: bool = False) -> int:
    """Enriquece um relatório já criado, sem reler nem tocar nos PDFs."""
    source = source.resolve()
    report_dir = source / APP_DIR
    plan_path = report_dir / "plano_organizacao.csv"
    if not plan_path.exists():
        print("Não encontrei o plano. Execute primeiro 01_ANALISAR_PDFS.bat.", file=sys.stderr)
        return 1
    with plan_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    if not rows:
        print("O plano está vazio.", file=sys.stderr)
        return 1
    for row in rows:
        for field in CSV_FIELDS:
            row.setdefault(field, "")
    enrich_rows(rows, report_dir, delay, retry_missing=retry_missing)
    assign_destinations(rows)
    make_report(source, rows, report_dir)
    print("\nEnriquecimento concluído. Abra novamente o relatório atualizado:")
    print(report_dir / "relatorio.html")
    return 0


def apply_plan(source: Path) -> int:
    source = source.resolve()
    report_dir = source / APP_DIR
    plan_path = report_dir / "plano_organizacao.csv"
    if not plan_path.exists():
        print("Nao encontrei o plano. Execute primeiro 01_ANALISAR_PDFS.bat.", file=sys.stderr)
        return 1
    destination_root = source / LIBRARY_DIR
    with plan_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    to_copy = [row for row in rows if row.get("status") == "UNICO" and row.get("destino_sugerido")]
    if not to_copy:
        print("O plano nao possui PDFs unicos para copiar.")
        return 1
    print(f"Copiando {len(to_copy)} PDFs para: {destination_root}")
    copied = missing = failed = 0
    log_rows: list[list[str]] = [["arquivo_original", "destino", "resultado", "detalhe"]]
    for index, row in enumerate(to_copy, 1):
        source_file = source / row["arquivo_original"]
        target = destination_root / row["destino_sugerido"]
        try:
            if not source_file.exists():
                missing += 1
                log_rows.append([row["arquivo_original"], str(target.relative_to(destination_root)), "NAO_ENCONTRADO", "Arquivo original nao existe mais"])
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == source_file.stat().st_size:
                log_rows.append([row["arquivo_original"], str(target.relative_to(destination_root)), "JA_EXISTIA", "Mantido sem copiar novamente"])
                continue
            shutil.copy2(source_file, target)
            copied += 1
            log_rows.append([row["arquivo_original"], str(target.relative_to(destination_root)), "COPIADO", ""])
        except Exception as exc:
            failed += 1
            log_rows.append([row["arquivo_original"], str(target.relative_to(destination_root)), "ERRO", f"{type(exc).__name__}: {exc}"])
        if index == 1 or index % 50 == 0 or index == len(to_copy):
            print(f"  {index}/{len(to_copy)}")
    log_path = report_dir / "resultado_copia.csv"
    with log_path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle, delimiter=";").writerows(log_rows)
    print(f"\nConcluido. Copiados: {copied}; ausentes: {missing}; erros: {failed}.")
    print(f"Sua nova biblioteca esta em: {destination_root}")
    print(f"Registro da operacao: {log_path}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Organizador seguro de PDFs")
    parser.add_argument("acao", choices=("analisar", "enriquecer", "aplicar"), nargs="?", default="analisar")
    parser.add_argument("--pasta", type=Path, help="Pasta raiz que contem os PDFs")
    parser.add_argument("--com-catalogos", action="store_true", help="Durante a análise, também consulta os catálogos públicos")
    parser.add_argument("--pausa", type=float, default=0.55, help="Pausa mínima entre consultas públicas, em segundos")
    parser.add_argument("--refazer-lacunas", action="store_true", help="Consulta novamente apenas itens sem metadados públicos no cache atual")
    args = parser.parse_args()
    source = args.pasta or choose_folder()
    if source is None:
        print("Nenhuma pasta foi selecionada.")
        return 1
    if not source.is_dir():
        print(f"Pasta invalida: {source}", file=sys.stderr)
        return 1
    if args.acao == "analisar":
        return analyse(source, enrich=args.com_catalogos, delay=max(0.0, args.pausa), retry_missing=args.refazer_lacunas)
    if args.acao == "enriquecer":
        return enrich_existing(source, delay=max(0.0, args.pausa), retry_missing=args.refazer_lacunas)
    return apply_plan(source)


if __name__ == "__main__":
    raise SystemExit(main())

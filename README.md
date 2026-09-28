# Bibliotecário

Organizador seguro de bibliotecas PDF para Windows. Ele inventaria milhares de
livros e artigos, extrai metadados do próprio arquivo, detecta duplicados
exatos e pode enriquecer o catálogo por fontes bibliográficas públicas.

> Os PDFs nunca são alterados, renomeados ou enviados pelo programa. A cópia
> organizada só é criada depois de uma revisão explícita do relatório.

## Recursos

- Varredura recursiva de PDFs e relatório HTML/CSV.
- Detecção de cópias exatas por SHA-256.
- Extração local de título, autor, ano, páginas e DOI quando existente.
- Consulta opcional a Google Books e Open Library para livros; Crossref para
  artigos científicos.
- ISBN-10, ISBN-13, editora, idioma, descrição curta, URL de catálogo e
  categorias públicas no relatório.
- Classificação ampla inspirada na CDD, usada como dado de catálogo.
- Organização segura em `Livros\Inicial\Autor\Título (Ano).pdf` e
  `Artigos\Inicial\Autor\Título (Ano).pdf`.
- Cache de consultas para interromper e retomar uma catalogação grande.

## Uso no Windows

1. Instale Python 3 e marque **Add Python to PATH** durante a instalação.
2. Baixe ou clone este repositório.
3. Execute `01_ANALISAR_PDFS.bat` e escolha a pasta com os PDFs.
4. Abra `__PDF_ORGANIZACAO__\relatorio.html` dentro da pasta analisada.
5. Execute `03_ENRIQUECER_CATALOGO.bat` para completar ISBN, editora e
   categorias usando fontes públicas. A operação pode ser interrompida e
   retomada.
6. Revise o relatório e execute `02_CRIAR_BIBLIOTECA_SEGURA.bat` somente
   quando estiver satisfeito. Os originais continuam intactos.

Consulte [docs/USO_WINDOWS.md](docs/USO_WINDOWS.md) para o fluxo completo.

## Estrutura

```text
organizar_biblioteca_pdf.py     núcleo da aplicação
01_ANALISAR_PDFS.bat            inventário local, sem alterações
02_CRIAR_BIBLIOTECA_SEGURA.bat  cria somente cópias organizadas
03_ENRIQUECER_CATALOGO.bat      consulta fontes públicas
requirements.txt                dependência de leitura de PDF
docs/                           documentação
```

## Privacidade e limites

Na etapa de enriquecimento, apenas título, autor e DOI detectado são enviados
às APIs públicas. O conteúdo dos PDFs permanece local. As fontes podem conter
edições diferentes; por isso o programa aceita uma correspondência apenas
quando título e, se disponível, autor apresentam boa similaridade. As colunas
`fonte_metadados` e `confianca_metadados` permitem revisar cada resultado.

Os arquivos de trabalho, relatórios, cache e a biblioteca copiada são locais e
estão excluídos do Git.

## Desenvolvimento

```powershell
py -3 -m pip install --user -r requirements.txt
py -3 organizar_biblioteca_pdf.py --help
```

O projeto usa apenas a biblioteca padrão do Python, exceto pelo PyMuPDF para
leitura dos PDFs.

Para executar os testes locais:

```powershell
py -3 -m unittest discover -s tests -v
```

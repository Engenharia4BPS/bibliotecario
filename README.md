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
- Busca de recuperação para lacunas: testa variações seguras do título e usa
  o padrão `Autor - Título` do nome do arquivo quando a primeira página do PDF
  não é uma boa capa bibliográfica.
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
6. Se ainda houver muitas lacunas, veja **Mais cobertura de metadados** abaixo
   e execute `04_BUSCAR_MAIS_METADADOS.bat`.
7. Revise o relatório e execute `02_CRIAR_BIBLIOTECA_SEGURA.bat` somente
   quando estiver satisfeito. Os originais continuam intactos.

Consulte [docs/USO_WINDOWS.md](docs/USO_WINDOWS.md) para o fluxo completo.

## Estrutura

```text
organizar_biblioteca_pdf.py     núcleo da aplicação
01_ANALISAR_PDFS.bat            inventário local, sem alterações
02_CRIAR_BIBLIOTECA_SEGURA.bat  cria somente cópias organizadas
03_ENRIQUECER_CATALOGO.bat      consulta fontes públicas
04_BUSCAR_MAIS_METADADOS.bat    tenta novamente apenas as lacunas
requirements.txt                dependência de leitura de PDF
docs/                           documentação
```

## Mais cobertura de metadados

O primeiro enriquecimento usa uma consulta cautelosa: ele prefere deixar um
item sem ISBN a colocar o ISBN de outro livro. A etapa `04` usa variações de
título, subtítulo e autor, além do nome do arquivo quando ele está no padrão
`Autor - Título`. Ela reaproveita os acertos anteriores e revisita somente os
itens que continuaram sem resultado.

Para ampliar a busca no Google Books, você pode usar uma chave gratuita da
API em seu próprio computador. Depois de criar uma chave restrita à **Google
Books API**, abra o Prompt de Comando e execute uma vez:

```bat
setx GOOGLE_BOOKS_API_KEY "COLE_A_SUA_CHAVE_AQUI"
```

Feche e abra novamente a janela de comandos antes de executar a etapa `04`.
Não coloque a chave no GitHub nem a envie para ninguém. A API do Google Books
aceita pesquisas de volumes públicos e a chave permite associar as consultas à
sua própria cota. Veja a [documentação oficial](https://developers.google.com/books/docs/v1/using).

Mesmo assim, parte de uma coleção pode não existir nos catálogos públicos: há
digitalizações antigas, edições locais, traduções com título diferente,
antologias, obras independentes e arquivos cujo texto inicial não é a capa.
Isso não bloqueia a organização: o programa mantém esses itens por autor e
título local, sem inventar um ISBN.

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

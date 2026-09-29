# Operação no Windows

## 1. Analisar sem risco

Execute `01_ANALISAR_PDFS.bat` e selecione a pasta raiz da coleção. O programa
analisa subpastas, mas ignora automaticamente `__PDF_ORGANIZACAO__` e
`Biblioteca_Organizada` para que uma nova execução não leia seus próprios
resultados.

O resultado fica na própria pasta analisada:

```text
__PDF_ORGANIZACAO__/
├── relatorio.html
├── inventario.csv
└── plano_organizacao.csv
```

Não há movimentação, renomeação ou exclusão de arquivo nessa etapa.

## 2. Enriquecer o catálogo

Execute `03_ENRIQUECER_CATALOGO.bat` e selecione a mesma pasta. A etapa usa:

- **Google Books** e **Open Library** para livros;
- **Crossref** para artigos com DOI ou referência bibliográfica.

Ela cria/atualiza `cache_metadados_publicos.json`. Se a máquina for desligada,
se a conexão cair ou se você encerrar a janela, execute novamente o mesmo
arquivo: resultados que já foram consultados são reaproveitados.

Para uma coleção de milhares de itens, deixe a etapa rodando por bastante
tempo. Evite executar duas cópias dela ao mesmo tempo sobre a mesma coleção.

## 2.1 Recuperar mais livros que ficaram sem resultado

O título lido da primeira página de um PDF pode ser uma página de copyright,
um sumário ou um título com subtítulo diferente do catálogo. Depois da etapa
2, execute `04_BUSCAR_MAIS_METADADOS.bat` para revisitar somente os itens que
continuaram sem dados públicos. Ela tenta o padrão de nome de arquivo
`Autor - Título` e pequenas variações seguras de título e autor.

Para aumentar a cobertura do Google Books, crie uma chave gratuita, restrita à
Google Books API, e registre-a uma vez no Windows:

```bat
setx GOOGLE_BOOKS_API_KEY "COLE_A_SUA_CHAVE_AQUI"
```

Feche a janela de comandos, abra novamente e então rode a etapa 2.1. A chave
fica somente no seu Windows; não a coloque em arquivos do projeto ou no GitHub.
Sem chave, o programa continua usando Open Library e Crossref, mas o Google
Books pode limitar ou recusar a sessão.

## 3. Conferir antes de copiar

Abra `relatorio.html` ou `plano_organizacao.csv` no Excel. A coluna
`confianca_metadados` registra a semelhança entre os dados do PDF e o registro
público escolhido. Resultados sem boa correspondência permanecem com os dados
locais, em vez de receber um título ou ISBN duvidoso.

As categorias são informação de catálogo; a pasta final é baseada em autor e
título, pois estes dados são mais estáveis para literatura geral.

## 4. Criar a biblioteca organizada

Quando o plano estiver aprovado, execute `02_CRIAR_BIBLIOTECA_SEGURA.bat`.
Ele cria `Biblioteca_Organizada` dentro da pasta escolhida e usa `copy2`,
preservando datas dos arquivos. O resultado é registrado em
`__PDF_ORGANIZACAO__/resultado_copia.csv`.

Os PDFs de origem nunca são removidos pelo programa.

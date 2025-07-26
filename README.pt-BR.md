
# Arqueokit

Arqueokit é um plugin desenvolvido para otimizar a análise e o processamento de dados geoespaciais aplicados à arqueologia.

### Funcionalidades:

-   Download de camadas comumente utilizadas  
    ✅ Baixar camadas do GeoServer do IPHAN  
    ✅ Baixar camadas do GeoServer da FUNAI
    
-   Geoprocessamento de grades de pontos mais rápido  
    ✅ Analisar e criar grades de pontos que maximizem o número de pontos dentro de um polígono (útil para prospecções)  
    ✅ Criar grades radiais de pontos a partir de pontos (método comum para delimitação de sítios arqueológicos no Brasil)
    
-   Mapas bivariados mais rápidos  
    ✅ Gerar um raster bivariado a partir de dois rasters  
    ✅ Gerar um raster RGB bivariado já simbolizado e fornecer uma legenda em PNG pronta para mapas
    
-   Gráficos sem sair do QGIS  
    ✅ Criar um gráfico _burndown_ com base em um atributo de data (útil para coordenação de equipes durante prospecções)  
    ✅ Criar um gráfico _Count Unique_ para um único atributo (usado durante amostragem de uso e cobertura do solo para manter o equilíbrio amostral)  
    ✅ Criar um gráfico de Comparação (Soma ou Média) de 2 a 5 atributos (ex.: comparar qual estrato possui mais artefatos)  
    ✅ Criar um gráfico de barras mostrando a soma de até 5 atributos numéricos agrupados (soma) por feição
    
-   Ordenação e atualização da Tabela de Atributos  
    ✅ Criar uma camada de pontos com ordenação por atributo (NO → SE)  
    ✅ Gerar atributos de Latitude e Longitude diretamente na tabela de atributos (atualização _in-place_)  
    ✅ Gerar automaticamente todos os atributos para fichas de prospecção arqueológica, incluindo id, Nome, coordenadas e campos padrão
    

-- Novos scripts serão adicionados futuramente

* IPHAN: Instituto do Patrimônio Histórico e Artístico Nacional (Brasil)  
* FUNAI: Fundação Nacional dos Povos Indígenas (Brasil)

----------

## Como instalar

### Dependências externas

O QGIS já vem com diversas bibliotecas Python integradas, mas algumas utilizadas pelo plugin precisam ser instaladas manualmente, pois não estão incluídas no ambiente Python padrão do QGIS. É necessário instalar as seguintes bibliotecas via `pip` (usando o **OSGeo4W Shell**):

bash

CopiarEditar

`pip install pandas matplotlib seaborn rasterio shapely pillow requests` 

### **Para que serve cada biblioteca:**

-   **pandas** → manipulação da tabela de atributos (DataFrames)
    
-   **matplotlib** → geração de gráficos (incluindo o gráfico _Burndown_)
    
-   **seaborn** → gráficos aprimorados e estilizados
    
-   **rasterio** → leitura e escrita de dados raster
    
-   **shapely** → operações geométricas avançadas em dados vetoriais
    
-   **pillow (PIL)** → processamento de imagens (ex.: criação de legendas em PNG)
    
-   **requests** → conexão com serviços externos (ex.: download de dados)
    

----------

### **Baixar e instalar o pacote no QGIS**

1.  **Baixar o plugin (.zip)**
    
    -   Clique no botão verde **Code** (no canto superior direito da lista de arquivos [nesta página](https://github.com/geraldopmj/Arqueokit/tree/main)).
        
    -   Selecione **Download ZIP**.
        
    -   O arquivo será baixado para o seu computador (não descompacte).
        
2.  **Abrir o QGIS**
    
    -   Vá em **Complementos → Gerenciar e Instalar Complementos…**
        
    -   Clique em **Instalar a partir de um ZIP** (botão no canto inferior esquerdo).
        
3.  **Instalar o plugin**
    
    -   Localize o arquivo `.zip` baixado.
        
    -   Clique em **Instalar complemento**.
        
    -   O QGIS instalará o plugin automaticamente.
        
4.  **Ativar o plugin**
    
    -   Após a instalação, verifique se o plugin está habilitado na lista de complementos instalados.
        
    -   Ele estará disponível no menu **Complementos** ou na barra de ferramentas.
        

> ⚠️ **Atenção:** Se estiver atualizando a partir de uma versão anterior, recomenda-se removê-la antes para evitar conflitos.

----------

## **Créditos & Contribuições**

**Autor:**

-   Geraldo Pereira de Morais Júnior
    
    -   _Analista/Desenvolvedor GIS & Arqueólogo_
        
    -   Email: **geraldo.pmj@gmail.com**
        

----------

## **Licença**

Este plugin está licenciado sob a **GNU Affero General Public License v3.0 (AGPL-3.0)**.

-   Você é livre para usar, modificar e distribuir este software, desde que qualquer versão modificada também seja lançada sob a licença **AGPL-3.0**.
    
-   Se você executar uma versão modificada deste software em um servidor e disponibilizá-la para usuários por meio de uma rede, deverá também fornecer o código-fonte das suas modificações.
    

**Texto completo da licença:**  
[GNU AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.en.html)

**Copyright © 2025 Geraldo Pereira de Morais Júnior**

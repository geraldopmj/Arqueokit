# Arqueokit

Arqueokit is a QGIS Processing plugin focused on archaeological workflows. It brings together tools for downloading Brazilian public heritage datasets, enriching survey layers, generating charts and reports, exporting web maps, computing raster products, and running machine-learning-based classification.

The plugin is exposed as a Processing provider inside QGIS, so its tools can be used from the Processing Toolbox and combined in models or scripts.

## What It Does

Arqueokit is intended to help archaeologists and GIS analysts with tasks such as:

- downloading public archaeology-related layers from FUNAI and IPHAN;
- preparing field survey layers and attributes;
- creating charts and summaries from survey data;
- exporting archaeological records and reports to PDF;
- generating web maps in HTML format;
- calculating spectral and bivariate raster products;
- classifying rasters with supervised machine learning;
- opening an interactive survey dashboard.

## Installation

Before opening QGIS and enabling the plugin, install any required external Python packages in the same Python environment used by QGIS. This is especially important for PDF export, charts, raster analysis, machine learning, web map export, and dashboard tools.

### Install Dependencies Before Opening QGIS

1. Close QGIS if it is already open.
2. On Windows with OSGeo4W-based QGIS installations, open the `OSGeo4W Shell` from the Start Menu.
3. In that shell, go to the plugin folder and run the pinned dependency installation command using the Python environment bundled with QGIS.
4. After installation finishes, start QGIS.
5. Install or enable the plugin.

Pinned dependency file:

- `requirements.txt`

Recommended installation command:

```bash
python -m pip install -r requirements.txt
```

Example for Windows with OSGeo4W:

1. Open `Start Menu` > `OSGeo4W`.
2. Click `OSGeo4W Shell`.
3. Change to the plugin folder.
4. Run:

```bash
cd "%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\Arqueokit"
python -m pip install -r requirements.txt
```

5. Wait for the installation to complete.
6. Open QGIS and then enable or install the plugin.

Important notes:

- Use the Python interpreter from QGIS, not the system Python, whenever your QGIS distribution uses its own environment.
- On Windows with OSGeo4W-based installations, prefer the OSGeo4W shell or the Python environment that ships with QGIS.
- If your platform or distribution manages packages differently, follow the installation method recommended for that QGIS build.

### Install From a ZIP Package in QGIS

1. Package the plugin folder as a ZIP file with the root directory named `Arqueokit`.
2. Open QGIS.
3. Go to `Plugins` > `Manage and Install Plugins...` > `Install from ZIP`.
4. Select the plugin ZIP file.
5. Enable the plugin if QGIS does not enable it automatically.
6. Open the `Processing Toolbox` and look for the `Arqueokit` provider.

### Manual Installation

1. Close QGIS.
2. Copy the `Arqueokit` folder into your QGIS plugins directory.
3. Start QGIS.
4. Enable `Arqueokit` in the QGIS plugin manager.

Typical plugin locations for QGIS 4:

- Windows: `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\`
- Linux: `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/`
- macOS: `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/`

## Python Dependencies

Some Arqueokit tools depend only on the standard QGIS Python environment, but several features require extra Python packages to be installed in the QGIS Python environment.

Potential external dependencies used by some algorithms include:

- `reportlab==4.4.10`
- `pandas==3.0.2`
- `matplotlib==3.10.8`
- `seaborn==0.13.2`
- `rasterio==1.5.0`
- `scikit-learn==1.8.0`
- `scipy==1.17.1`
- `joblib==1.5.3`
- `scikit-image==0.26.0`
- `Pillow==12.2.0`
- `folium==0.20.0`
- `flet==0.84.0`
- `flet-desktop==0.84.0`
- `flet-map==0.84.0`

Depending on your QGIS installation, some tools may also rely on packages that are commonly available with QGIS, such as `numpy`.

If a tool fails because a dependency is missing, install the pinned package set into the same Python environment used by QGIS. On many systems this means using the Python interpreter bundled with QGIS instead of the system-wide Python interpreter.

## Internet and External Services

Some tools depend on internet access and on the availability of external public services. In particular, dataset download tools rely on third-party servers maintained by Brazilian institutions such as FUNAI and IPHAN. If those services are offline, unavailable, rate-limited, or changed by their maintainers, the related algorithms may fail or return incomplete results.

## Features

The `Arqueokit` provider exposes the following processing algorithms in QGIS.

### Public Data Download

- `Download de Camadas da FUNAI`: loads selected FUNAI WFS layers directly into the current QGIS project.
- `Download de Camadas IPHAN`: loads selected IPHAN WFS layers directly into the current QGIS project.

### Survey Attribute Tools

- `Atualizar Longitude e Latitude`: writes or updates longitude and latitude attributes for features.
- `Inicializar Atributos da Ficha de Prospecção`: structures point survey layers for archaeological record forms by recreating standard fields, redefining IDs, updating names, and recalculating coordinates.
- `Ordenar Pontos de NW para SE`: orders points using a northwest-to-southeast logic for structured field workflows.

### Graphs and Analytical Summaries

- `Contagem de Valores Únicos em Atributo`: counts unique values in a categorical field and generates a chart.
- `Soma ou Média comparando até 5 Atributos`: compares up to five numeric attributes and generates a sum or mean chart.
- `Soma de Atributos por Feição`: summarizes values by feature groups and exports a chart.
- `Gráfico Burndown Temporal`: produces temporal progress-style graphics for monitoring fieldwork or production.

### Geoprocessing Tools

- `Grade com Melhor Cobertura (com ângulo)`: evaluates point-grid configurations, offsets, and angles to maximize coverage inside a polygon.
- `Gerar Pontos Radiais`: generates radial point patterns from an input reference.
- `Juntar extremidades soltas de linhas`: connects nearby loose line endpoints for cleanup and topological correction workflows.

### PDF Outputs

- `Exportar Fichas de Prospecção`: exports archaeological survey record sheets to PDF.
- `Exportar Relatório Pós-Campo`: exports a survey report PDF with formatted content and optional logos.

### WebGIS

- `Exportar WebMapa`: exports an interactive HTML web map using Folium, combining vector layers and rendered rasters.

### Raster and Remote Sensing

- `Raster Bivariado`: combines two raster inputs into a bivariate output.
- `Raster Bivariado RGB`: generates RGB-style bivariate raster outputs.
- `Geração de Índices Espectrais`: computes spectral indices from multiband rasters and can optionally write separate outputs or stacked rasters.

### Machine Learning

- `Classificação Supervisionada RF`: performs supervised raster classification using Random Forest and related raster-derived features.

This workflow can include:

- band mapping;
- spectral indices;
- local entropy features;
- optional validation samples;
- model export and reload;
- classified raster export;
- JSON metric reports.

### Dashboard

- `Dashboard de Prospecção`: opens an interactive dashboard for point-based archaeological survey review.

## Processing Catalog

- `Download de Camadas da FUNAI`: downloads selected FUNAI public layers and adds them to the current QGIS project.
- `Download de Camadas IPHAN`: downloads selected IPHAN public layers and adds them to the current QGIS project.
- `Atualizar Longitude e Latitude`: removes and recreates longitude and latitude fields, then fills them from point geometries.
- `Inicializar Atributos da Ficha de Prospecção`: prepares a point layer for archaeological record forms by recreating standard fields, redefining IDs, updating names, and recalculating coordinates.
- `Ordenar Pontos de NW para SE`: creates or recreates an ordering field and fills it according to northwest-to-southeast spatial order.
- `Contagem de Valores Únicos em Atributo`: counts unique categorical values and exports a frequency chart.
- `Soma ou Média comparando até 5 Atributos`: compares up to five numeric fields using a sum or mean chart.
- `Soma de Atributos por Feição`: summarizes selected numeric attributes by feature label and exports a chart.
- `Gráfico Burndown Temporal`: creates a burndown chart from date-based progress information.
- `Grade com Melhor Cobertura (com ângulo)`: searches offsets and angles to build a point grid with the best polygon coverage.
- `Gerar Pontos Radiais`: generates radial points from input features using configurable spacing and limits.
- `Juntar extremidades soltas de linhas`: snaps and connects nearby dangling line endpoints.
- `Exportar Fichas de Prospecção`: generates PDF sheets for archaeological survey point records.
- `Exportar Relatório Pós-Campo`: generates a formatted post-fieldwork PDF report.
- `Exportar WebMapa`: exports an interactive HTML web map with vectors and rasters.
- `Raster Bivariado`: combines two rasters into a classified bivariate raster.
- `Raster Bivariado RGB`: combines two rasters into an RGB bivariate raster and also exports a legend image.
- `Geração de Índices Espectrais`: computes selected spectral indices from multiband raster inputs.
- `Classificação Supervisionada RF`: runs supervised raster classification with Random Forest, optional validation, and report outputs.
- `Dashboard de Prospecção`: opens an interactive Flet-based dashboard for survey analysis.

## How To Use

1. Open QGIS and enable the plugin.
2. Open the `Processing Toolbox`.
3. Expand the `Arqueokit` provider.
4. Run the desired algorithm.
5. Review parameter descriptions inside the QGIS dialog before execution, especially for tools that depend on external services or optional Python packages.

## Notes and Limitations

- Not every tool has the same dependency profile. A simple attribute tool may work in a basic QGIS setup, while machine learning, charting, PDF export, dashboard, or web map tools may need extra libraries.
- External services can change their endpoints, schemas, permissions, or availability without notice.
- Large rasters and complex machine learning workflows may require significant memory and processing time.
- Results generated by analytical and machine learning tools should always be reviewed by a qualified user before being used in formal decision-making.

## Repository and Support

- Homepage: [https://github.com/geraldopmj/Arqueokit](https://github.com/geraldopmj/Arqueokit)
- Issue tracker: [https://github.com/geraldopmj/Arqueokit/issues](https://github.com/geraldopmj/Arqueokit/issues)

## License

Arqueokit is distributed under the GNU General Public License, version 2 or any later version. See the [LICENSE](./LICENSE) file for the full license text.

## Warranty Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.

In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use of or other dealings in the software.

<img src="https://github.com/geraldopmj/Arqueokit/blob/main/icon.png" width="75" height="75">

# Arqueokit

[English](README.md) | [Português (Brasil)](README.pt-BR.md)

Archeokit is a QGIS plugin designed to streamline the analysis and processing of geospatial data for archaeology.

### Features:
- Download layers commonly used  
✅ Download layers from IPHAN’s GeoServer  
✅ Download layers from FUNAI's GeoServer  
- Geoprocessing faster grids  
✅ Analyze and create point grids that maximize the number of points inside a polygon (useful for surveying)  
✅ Create radial point grids from points (common method for archaeological site delimitation in Brazil)
- Correct Data faster  
✅ Connect start and end points of line layers (up to the threshold).
- Faster Bivariate maps  
✅ Generate a bivariate raster from two rasters  
✅ Generate a bivariate RGB raster, already symbolized, and provide a PNG legend ready for layouts  
- Charts without leaving QGIS  
✅ Create a burndown chart based on a date attribute (useful for team coordination during surveying)  
✅ Create a Count Unique graph for a single attribute (used during LULC sampling to maintain sample balance)  
✅ Create a Comparison graph (Sum or Mean) across 2 to 5 attributes (e.g., compare which stratum has more artifacts)  
✅ Create a bar chart showing the sum of up to 5 numeric attributes grouped (sum) by feature  
- Ordering and updating Attribute Table  
✅ Create an attribute ordering point layer (NW → SE)  
✅ Generate Latitude and Longitude attributes directly in the attribute table (in-place update)  
✅ Generate all attributes for archaeological survey forms (Ficha Arqueológica) automatically, including id, Name, coordinates, and default fields

-- Looking forward to add many more scripts

\* **IPHAN**: Instituto do Patrimônio Histórico e Artístico Nacional (Brazil)

\* **FUNAI**: Fundação Nacional dos Povos Indígenas (Brazil)

--------------------------------------------------
## How to install
### External dependencies
QGIS already comes with several built-in Python libraries, but some used by the plugin must be installed manually, as they are not included in the standard QGIS Python environment. You must install the following external libraries via `pip` (using the **OSGeo4W Shell**):

    pip install pandas matplotlib seaborn rasterio shapely pillow requests

### **What each library is for:**

-   **pandas** → attribute table manipulation (DataFrames)
-   **matplotlib** → graph generation
-   **seaborn** → enhanced and styled graphs
-   **rasterio** → reading and writing raster data
-   **shapely** → advanced geometric operations for vector data
-   **pillow (PIL)** → image processing (e.g., creation of PNG legends)
-   **requests** → connecting with external services (e.g., downloading data)

### **Download and install the package in QGIS**

1.  **Download the plugin (.zip)**
    -   Click the green **Code** button (at the top-right of the file list in [this page](https://github.com/geraldopmj/Arqueokit/tree/main)).
    -   Select **Download ZIP**.
    -   The file will be downloaded to your computer.
    -   Extract the contents of the ZIP file.
    -   Rename the extracted folder from Arqueokit-main to Arqueokit (the name must match the plugin name exactly).
    -   ZIP the renamed folder (QGIS only accept .zip files).
   
2.  **Open QGIS**
    -   Go to **Plugins → Manage and Install Plugins…**
    -   Click on **Install from ZIP** (button in the bottom-left corner).
        
3.  **Install the plugin**
    -   Locate the `.zip` file.
    -   Click **Install Plugin**.
    -   QGIS will automatically install the plugin.
        
4.  **Activate the plugin**
    -   After installation, check if the plugin is enabled in the list of installed plugins.
    -   It will be available in the **Processing Toolbox**.
        
> ⚠️ **Note:** If you are updating from a previous version, it is recommended to remove it first to avoid conflicts.


 ## **Credits & Contributions**

**Author:**

-   Geraldo Pereira de Morais Júnior
    -   _Data Scientis, GIS Analyst/Developer & Archaeologist_
    -   Email: **geraldo.pmj@gmail.com**   
## **License**

This plugin is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.
-   You are free to use, modify, and distribute this software, as long as any modified version is also released under the **AGPL-3.0** license.
-   If you run a modified version of this software on a server and make it available to users over a network, you must also provide the source code of your modifications.

**Full license text:**  
[GNU AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.en.html)

**Disclaimer:**
This software is provided “as is”, without any express or implied warranty.
The author assumes no liability for damages arising from the use of this software.

**Copyright © 2025 Geraldo Pereira de Morais Júnior**

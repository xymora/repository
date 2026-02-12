# 📖 Data Dictionary: Netflix Content Catalog

| Column | Description | Data Type |
| :--- | :--- | :--- |
| `type` | Classification of the content (Movie or TV Show). | Categorical |
| `title` | Official name of the movie or series. | String |
| `director` | Name of the director (Anonymous if missing). | String |
| `cast` | Principal actors involved in the production. | String |
| `country` | Country where the content was produced. | String |
| `date_added` | Date when the content was added to the platform. | Datetime |
| `release_year` | Original release year of the content. | Integer |
| `listed_in` | Genres or categories assigned to the title. | String |
| `description` | Brief summary of the plot used for NLP modeling. | Text |

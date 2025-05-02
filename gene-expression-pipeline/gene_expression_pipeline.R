library(ggplot2)
library(dplyr)
library(pheatmap)
library(DESeq2)

# Cargar datos
expr <- read.csv("gene_expression_data.csv", row.names = 1)
meta <- read.csv("sample_metadata.csv")

# Crear objeto DESeq2
dds <- DESeqDataSetFromMatrix(countData = round(expr),
                              colData = meta,
                              design = ~ Condition)

# Ejecutar análisis
dds <- DESeq(dds)
res <- results(dds)

# Resumen y genes significativos
summary(res)
sig_genes <- subset(res, padj < 0.05)

# Volcán
res_df <- as.data.frame(res)
res_df$Gene <- rownames(res_df)
ggplot(res_df, aes(x=log2FoldChange, y=-log10(padj))) +
    geom_point(alpha=0.4) +
    geom_vline(xintercept=c(-1, 1), linetype="dashed", color="red") +
    geom_hline(yintercept=-log10(0.05), linetype="dashed", color="blue") +
    theme_minimal() +
    labs(title="Volcano Plot", x="log2 Fold Change", y="-log10 Adjusted P-value")
ggsave("volcano_plot.png")

# Heatmap de genes significativos
sig_expr <- expr[rownames(expr) %in% rownames(sig_genes), ]
pheatmap(log2(sig_expr + 1), cluster_rows=TRUE, cluster_cols=TRUE, 
         main="Differentially Expressed Genes (Heatmap)")

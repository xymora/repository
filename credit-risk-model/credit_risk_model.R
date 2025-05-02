library(ggplot2)
library(dplyr)
library(pROC)

# Cargar datos
df <- read.csv("credit_risk_data.csv")

# Ajustar regresión logística
model <- glm(Defaulted ~ AnnualRevenue + YearsInOperation + CreditScore + LoanAmount,
             data = df, family = "binomial")

# Predicciones
df$predicted_prob <- predict(model, type = "response")

# Curva ROC
roc_obj <- roc(df$Defaulted, df$predicted_prob)
auc_val <- auc(roc_obj)

# Imprimir resumen del modelo y AUC
print(summary(model))
cat("AUC:", auc_val, "\n")

# Gráfica de la curva ROC
png("credit_risk_roc.png", width = 600, height = 400)
plot(roc_obj, col = "blue", lwd = 2, main = "ROC Curve for Credit Risk Model")
abline(a = 0, b = 1, lty = 2, col = "gray")
dev.off()

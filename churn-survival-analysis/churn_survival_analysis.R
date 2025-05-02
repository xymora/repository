# Cargar librerías
library(survival)
library(survminer)
library(dplyr)

# Cargar datos
data <- read.csv("customer_churn_survival.csv")

# Crear objeto de supervivencia
surv_obj <- Surv(time = data$SubscriptionLength, event = data$Churned)

# Kaplan-Meier por tipo de plan
km_fit <- survfit(surv_obj ~ PlanType, data = data)

# Gráfico Kaplan-Meier
ggsurvplot(km_fit, data = data, pval = TRUE,
           title = "Survival Curve by Plan Type",
           xlab = "Months of Subscription", ylab = "Survival Probability",
           risk.table = TRUE)

# Modelo de Cox
cox_model <- coxph(surv_obj ~ Age + PlanType + Region, data = data)

# Resumen del modelo
summary(cox_model)

# Gráfico de HR
ggforest(cox_model, data = data)

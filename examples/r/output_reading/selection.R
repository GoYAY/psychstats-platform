source("_common.R")
d <- read.csv("cross_sectional_survey.csv")
full <- lm(well_being~stress+social_support+age,d); selected <- step(full,direction="both",trace=1)
print(summary(full)); print(summary(selected))
finish(c(full_aic=AIC(full),selected_aic=AIC(selected),selected_r_squared=summary(selected)$r.squared),list(coefficients=data.frame(term=rownames(coef(summary(selected))),coef(summary(selected)),check.names=FALSE)))


source("_common.R")
d <- read.csv("cross_sectional_survey.csv"); fit <- lm(well_being~stress,d); print(summary(fit))
ci <- unname(confint(fit)["stress",])
finish(c(intercept=unname(coef(fit)[1]),slope=unname(coef(fit)["stress"]),ci_lower=ci[1],ci_upper=ci[2],r_squared=summary(fit)$r.squared),list(coefficients=data.frame(term=rownames(coef(summary(fit))),coef(summary(fit)),check.names=FALSE)))


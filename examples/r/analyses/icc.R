source("examples/r/analyses/_common.R")
d <- read_data("nested_classrooms")
fit <- nlme::lme(achievement ~ 1, random=~1|class_id, data=d, method="REML")
v <- as.numeric(nlme::VarCorr(fit)[, "Variance"])[1:2]
emit(c(icc=v[1]/sum(v), class_variance=v[1], residual_variance=v[2], converged=1))

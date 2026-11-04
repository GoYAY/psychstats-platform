source("examples/r/analyses/_common.R")
d <- read_data("cross_sectional_survey")
fit <- cor.test(d$social_support, d$well_being, method="pearson")
emit(c(r=unname(fit$estimate), p_value=fit$p.value, n=nrow(d)))

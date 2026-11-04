source("examples/r/analyses/_common.R")
d <- read_data("cross_sectional_survey")
fit <- t.test(d$stress)
emit(c(estimate=unname(fit$estimate), ci_lower=unname(fit$conf.int[1]), ci_upper=unname(fit$conf.int[2])))

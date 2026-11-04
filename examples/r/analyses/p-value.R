source("examples/r/analyses/_common.R")
d <- read_data("learning_experiment")
fit <- t.test(gain ~ condition,data=d)
emit(c(p_value=fit$p.value, t_statistic=unname(fit$statistic), df=unname(fit$parameter)))

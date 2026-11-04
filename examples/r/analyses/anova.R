source("examples/r/analyses/_common.R")
d <- read_data("learning_experiment")
fit <- aov(post_score ~ condition, data=d)
tab <- summary(fit)[[1]]
emit(c(f_statistic=tab[1,"F value"], p_value=tab[1,"Pr(>F)"], n=nrow(d)))

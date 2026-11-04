source("examples/r/analyses/_common.R")
d <- read_data("cross_sectional_survey")
emit(c(n=nrow(d), stress_mean=mean(d$stress), stress_sd=sd(d$stress), stress_median=median(d$stress)))

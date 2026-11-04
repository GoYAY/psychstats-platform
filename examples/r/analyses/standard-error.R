source("examples/r/analyses/_common.R")
d <- read_data("cross_sectional_survey")
se <- sd(d$stress)/sqrt(sum(!is.na(d$stress)))
emit(c(standard_error=se, sample_sd=sd(d$stress), n=nrow(d)))
